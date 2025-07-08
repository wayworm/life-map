from datetime import date
from dateutil.relativedelta import relativedelta
from flask import Flask, flash, redirect, render_template, request, session, g, jsonify
from flask_session import Session
from functools import wraps
import traceback
from werkzeug.security import check_password_hash, generate_password_hash
from google_calendar import *
from db import get_db

# TODO: Link to Google Calendar.
# TODO: fix depreciated line: "now = datetime.datetime.utcnow().isoformat() + "Z"  # 'Z' indicates UTC time "

# DONE:
# TODO: Project pages due date --> years, months, weeks, days dependings on timescale 
# TODO: Add functionality to reorder the tasks by drag and drop.
# TODO: Add a maximum value of 6 layers of subtasks. Present a message to screen if they try to go deeper.
# TODO: make the drag and drop easier to work with - it's hard to turn something into a subtask 
#       if the target parent doesn't already have a subtask
# TODO: Add a way to track whether something was minimsed, so it doesn't default to open.
# TODO: if a task is completed, it's minimisation behaviour should change, so the whole card hides, and we have a button to reshow hidden cards
# TODO: Subtasks can no longer be due after their parent tasks,
# TODO: Make nav bar stick to top of page when scrolling down.
# TODO: Logic to disallow a subtask to have more hours attributed to it than it's parent task.



# Configure application
app = Flask(__name__)

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

def error_page(message, code=400):
    """Render error page to user."""
    return render_template("error_page.html", code=code, message=message), code


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get("user_id") is None:
            return redirect("/login")
        return f(*args, **kwargs)
    return decorated_function

def build_task_tree(tasks_flat_list):
    task_map = {}
    for task_row in tasks_flat_list:
        task_dict = dict(task_row)
        # Match keys to schema for consistency
        task_dict['item_id'] = task_dict['item_id']
        task_dict['parent_item_id'] = task_dict['parent_item_id']
        task_dict['is_completed'] = bool(task_dict['is_completed'])
        # ✨ ADDITION: Handle the new is_minimized state
        task_dict['is_minimized'] = bool(task_dict['is_minimized'])
        task_dict['subtasks'] = []
        task_dict['planned_hours'] = task_dict['planned_hours']
        task_map[task_dict['item_id']] = task_dict
    
    tree = []
    for item_id, task in task_map.items():
        if task['parent_item_id'] and task['parent_item_id'] in task_map:
            task_map[task['parent_item_id']]['subtasks'].append(task)
        elif not task['parent_item_id']:
            tree.append(task)

    def calculate_rolled_up_hours(task):
        if not task['subtasks']:
            task['calculated_planned_hours'] = task.get('planned_hours') or 0.0
            return task['calculated_planned_hours']
        
        total_hours = 0.0
        for subtask in task['subtasks']:
            total_hours += calculate_rolled_up_hours(subtask)
        
        task['calculated_planned_hours'] = total_hours
        return total_hours

    def sort_and_calculate_recursive(tasks_list):
        tasks_list.sort(key=lambda t: t.get('display_order', t['item_id']))
        for t in tasks_list:
            if t['subtasks']:
                sort_and_calculate_recursive(t['subtasks'])
            calculate_rolled_up_hours(t)

    sort_and_calculate_recursive(tree)
    return tree

def get_username(user_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""SELECT username FROM users WHERE user_id = ?""", (user_id,))
    username_row = cursor.fetchone()
    return username_row[0] if username_row else None

def format_date_difference(target_date_str: str) -> str:
    if not target_date_str: return "No due date"
    target_date = date.fromisoformat(target_date_str)
    today = date.today()
    delta = relativedelta(target_date, today)
    if target_date < today: return "Date has passed"
    parts = []
    if delta.years: parts.append(f"{delta.years} year{'s' if delta.years != 1 else ''}")
    if delta.months: parts.append(f"{delta.months} month{'s' if delta.months != 1 else ''}")
    if delta.days: parts.append(f"{delta.days} day{'s' if delta.days != 1 else ''}")
    return " ".join(parts) or "Today"

@app.teardown_appcontext
def close_db(e=None):
    lifemap_db = g.pop('lifemap_db', None)
    if lifemap_db is not None:
        lifemap_db.close()

@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response

# --- All other routes remain the same ---
@app.route("/")
@login_required
def index():
    return redirect("/projects")

@app.route("/account", methods=["GET"])
@login_required
def account():
    user_id = session["user_id"]
    return render_template("account.html", username=get_username(user_id))

@app.route("/change_username", methods=["POST"])
@login_required
def change_username():
    user_id = session["user_id"]
    new_username = request.form.get("username")
    if not new_username:
        return error_page("NO new username entered", 400)
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("""UPDATE users SET username = ? WHERE user_id = ?""", (new_username, user_id))
        conn.commit()
        flash("Username changed successfully!", "success")
        return redirect("/")
    except Exception as e:
        conn.rollback()
        flash(f"Error changing username: {e}", "danger")
        return error_page("Error changing username", 500)

@app.route("/reset_password", methods=["POST"])
@login_required
def reset_password():
    user_id = session["user_id"]
    current_password = request.form.get("current_password")
    new_password = request.form.get("new_password")
    confirmation = request.form.get("confirmation")

    if not current_password or not new_password or not confirmation:
        return error_page("All password fields must be filled.", 400)
    if new_password != confirmation:
        return error_page("New password and confirmation do not match.", 400)

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""SELECT password_hash FROM users WHERE user_id = ?""", (user_id,))
    user_hash_record = cursor.fetchone()
    if user_hash_record is None:
        return error_page("User not found.", 404)
    stored_hash = user_hash_record["password_hash"]

    if check_password_hash(stored_hash, current_password):
        if check_password_hash(stored_hash, new_password):
            return error_page("New password cannot be the same as current password.", 400)
        new_hashed_password = generate_password_hash(new_password, method='scrypt', salt_length=16)
        try:
            cursor.execute("""UPDATE users SET password_hash = ? WHERE user_id = ?""", (new_hashed_password, user_id))
            conn.commit()
            flash("Password changed successfully!", "success")
            return redirect("/")
        except Exception as e:
            conn.rollback()
            flash(f"Error resetting password: {e}", "danger")
            return error_page("Error resetting password", 500)
    else:
        return error_page("Incorrect current password.", 403)


@app.route("/login", methods=["GET", "POST"])
def login():
    session.clear()
    if request.method == "POST":
        login_input = request.form.get("username-or-email")
        password = request.form.get("password")
        if not login_input:
            return error_page("must provide username or e-mail", 403)
        if not password:
            return error_page("must provide password", 403)

        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("""SELECT * FROM users WHERE username = ? OR email = ? LIMIT 1""", (login_input, login_input))
        row = cursor.fetchone()

        if not row or not check_password_hash(row["password_hash"], password):
            lowered = login_input.lower()
            cursor.execute("""SELECT * FROM users WHERE email = ? LIMIT 1""", (lowered,))
            row = cursor.fetchone()
            if not row or not check_password_hash(row["password_hash"], password):
                return error_page("invalid username and/or password", 403)
            
        session["user_id"] = row["user_id"]
        return redirect("/")
    else:
        return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        email = request.form.get("email")
        confirmation = request.form.get("confirmation")

        if not username: return error_page("must provide username", 400)
        elif not password: return error_page("must provide password", 400)
        elif not confirmation: return error_page("must confirm password", 400)
        elif password != confirmation: return error_page("Passwords don't match", 400)
        if len(password) < 8: return error_page("Password must be at least 8 characters long.")
        if not any(char.isdigit() for char in password): return error_page("Password must contain at least one digit.")
        if not any(char.isupper() for char in password): return error_page("Password must contain at least one uppercase letter.")
        if not any(char.islower() for char in password): return error_page("Password must contain at least one lowercase letter.")

        conn = get_db()
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT user_id FROM users WHERE username = ?", (username,))
            if cursor.fetchone(): return error_page("Username already taken.", 400)
            hashed_password = generate_password_hash(password, method='scrypt', salt_length=16)
            cursor.execute("""INSERT INTO users (username, email, password_hash) VALUES (?,?,?) """, (username, email, hashed_password))
            conn.commit()
            flash("Registered successfully! Please log in.")
            return redirect("/login")
        except Exception as e:
            traceback.print_exc()
            conn.rollback()
            return error_page(f"Registration error: {e}")
    else:
        return render_template("register.html")

@app.route("/newProject", methods=["GET", "POST"])
@login_required
def newProject():
    user_id = session["user_id"]
    if request.method == "POST":
        title = request.form.get("title")
        description = request.form.get("description")
        start_date = request.form.get("start_date")
        due_date = request.form.get("end_date")
        
        if not title: return error_page("No Title entered.", 400)
        if not description: return error_page("No description entered.", 400)

        conn = get_db()
        cursor = conn.cursor()
        try:
            cursor.execute("""SELECT project_id FROM projects WHERE user_id = ? AND name = ?""", (user_id, title))
            if cursor.fetchone(): return error_page("You already have a project with this name.", 400)
            
            cursor.execute("""INSERT INTO projects (user_id, name, description, end_date, start_date) VALUES (?, ?, ?, ?, ?)""", (user_id, title, description, due_date, start_date))
            project_id = cursor.lastrowid

            cursor.execute("""INSERT INTO work_items (project_id, parent_item_id, name, description, planned_hours) VALUES (?, ?, ?, ?, ?)""", (project_id, None, title, description, None))

            conn.commit()
            flash(f"Project '{title}' created successfully!")
            return redirect("/projects")
        except Exception as e:
            traceback.print_exc()
            conn.rollback()
            return error_page(f"Error creating project: {e}")
    else:
        return render_template("newProject.html", username=get_username(user_id))

@app.route("/projects/<int:project_id>/edit", methods=["GET", "POST"])
@login_required
def edit_project(project_id):
    user_id = session["user_id"]
    conn = get_db()
    cursor = conn.cursor()

    if request.method == "GET":
        cursor.execute("""SELECT name, description FROM projects WHERE user_id = ? AND project_id = ?""", (user_id, project_id))
        project = cursor.fetchone()
        if project is None: return error_page("Project not found or you don't have permission to edit.", 404)
        return render_template("editProject.html", current_project=dict(project), project_id=project_id, username=get_username(user_id))

    elif request.method == "POST":
        new_title = request.form.get("projectTitle")
        new_description = request.form.get("projectDescription")

        if not new_title: return jsonify({"success": False, "error": "New project title cannot be empty."}), 400

        try:
            cursor.execute("SELECT 1 FROM projects WHERE user_id = ? AND project_id = ?", (user_id, project_id))
            if not cursor.fetchone(): return jsonify({"success": False, "error": "Project not found or not authorized."}), 403

            cursor.execute("""UPDATE projects SET name = ?, description = ? WHERE project_id = ?""", (new_title, new_description, project_id))
            
            cursor.execute("""
                UPDATE work_items SET name = ?, description = ?
                WHERE project_id = ? AND parent_item_id IS NULL
            """, (new_title, new_description, project_id))

            conn.commit()
            flash("Project updated successfully!", "success")
            return redirect("/projects")
        except Exception as e:
            traceback.print_exc()
            conn.rollback()
            return jsonify({"success": False, "error": f"Internal server error: {e}"}), 500

@app.route("/details/<int:project_id>")
@login_required
def tasks(project_id):
    user_id = session["user_id"]
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""SELECT name, description FROM projects WHERE user_id = ? AND project_id = ?""", (user_id, project_id))
    project_details = cursor.fetchone()

    if project_details is None:
        return error_page("Project not found or you are not authorized.", 404)

    project_name = project_details["name"]
    cursor.execute("""SELECT * FROM work_items WHERE project_id = ?""", (project_id,))
    tasks_flat_list = cursor.fetchall()
    tree = build_task_tree(tasks_flat_list)

    return render_template(
        'tasks.html',
        tasks=tree,
        project_id=project_id,
        project_name=project_name,
        username=get_username(user_id),
        project_details=project_details)

@app.route("/projects", methods=["GET", "POST"])
@login_required
def projects_list():
    if request.method == "GET":
        conn = get_db()
        cursor = conn.cursor()
        user_id = session["user_id"]

        cursor.execute("""SELECT * FROM projects WHERE user_id = ? ORDER BY end_date ASC""", (user_id,))
        rows = [dict(row) for row in cursor.fetchall()]
        for row in rows:
            row["readable_due_date"] = format_date_difference(row["end_date"])

        return render_template(
            "projects.html",
            projects=rows,
            username=get_username(user_id))
    else:
        return error_page("Request Error, Only GET requests accepted.", 403)

@app.route("/projects/<int:project_id>/delete", methods=["POST"])
@login_required
def delete_project(project_id):
    user_id = session["user_id"]
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT 1 FROM projects WHERE project_id = ? AND user_id = ?", (project_id, user_id))
        if not cursor.fetchone():
            flash("Project not found or you don't have permission to delete it.", "danger")
            return redirect("/projects")

        cursor.execute("DELETE FROM projects WHERE project_id = ?", (project_id,))
        conn.commit()
        flash("Project deleted successfully!", "success")
    except Exception as e:
        conn.rollback()
        flash(f"An error occurred while deleting the project: {e}", "danger")
    return redirect("/projects")

# Add this import at the top of your Flask app file
from google_calendar import pushOutgoingEvents
import traceback

# Your existing Flask app setup...

@app.route("/save-tasks", methods=["POST"])
@login_required
def save_tasks():
    user_id = session["user_id"]
    conn = get_db()
    cursor = conn.cursor()

    try:
        data = request.get_json()
        project_id = data.get("project_id")
        tasks_data = data.get("tasks", [])
        deleted_item_ids = data.get("deleted_item_ids", [])

        cursor.execute("SELECT 1 FROM projects WHERE user_id = ? AND project_id = ?", (user_id, project_id))
        if not cursor.fetchone():
            return jsonify({"error": "Project not found or not owned by user."}), 403

        if deleted_item_ids:
            clean_ids = [int(i) for i in deleted_item_ids if str(i).isdigit()]
            if clean_ids:
                placeholders = ','.join(['?'] * len(clean_ids))
                cursor.execute(f"DELETE FROM work_items WHERE item_id IN ({placeholders}) AND project_id = ?", clean_ids + [project_id])

        id_map = {}
        def process_task_list(task_list, parent_db_id=None):
            for task in task_list:
                # ... (your existing code for getting task properties: name, description, etc.)
                client_id = task["item_id"]
                name = task["name"]
                description = task.get("description")
                due_date = task.get("due_date") or None # e.g., "2025-09-15"
                is_completed = 1 if task.get("is_completed", False) else 0
                is_minimized = 1 if task.get("is_minimized", False) else 0
                display_order = task.get("display_order", 0)
                planned_hours_input = task.get("planned_hours")
                # ... (your existing code for planned hours)
                planned_hours_to_save = None
                if not task.get("subtasks") and planned_hours_input not in ['', None]:
                    try:
                        planned_hours_to_save = float(planned_hours_input)
                    except (ValueError, TypeError):
                        planned_hours_to_save = None

                current_db_id = None
                # ... (your existing INSERT/UPDATE logic)
                if isinstance(client_id, str) and client_id.startswith("new-"):
                    cursor.execute("""
                        INSERT INTO work_items (project_id, parent_item_id, name, description, due_date, is_completed, display_order, planned_hours, is_minimized)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (project_id, parent_db_id, name, description, due_date, is_completed, display_order, planned_hours_to_save, is_minimized))
                    new_db_id = cursor.lastrowid
                    id_map[client_id] = new_db_id
                    current_db_id = new_db_id
                
                elif str(client_id).isdigit():
                    current_db_id = int(client_id)
                    cursor.execute("""
                        UPDATE work_items
                        SET name = ?, description = ?, due_date = ?, is_completed = ?,
                            display_order = ?, parent_item_id = ?, planned_hours = ?, is_minimized = ?
                        WHERE item_id = ? AND project_id = ?
                    """, (name, description, due_date, is_completed, display_order, parent_db_id, planned_hours_to_save, is_minimized, current_db_id, project_id))
                else:
                    continue

                # ✨ PUSH TO GOOGLE CALENDAR (Local/Single-User Version) ✨
                # If the task has a due date, create a calendar event.
                if due_date:
                    print(f"Task '{name}' has a due date. Preparing to create calendar event.")
                    # Format the data for a full-day Google Calendar event.
                    event_data = {
                      'summary': name,
                      'description': description or "No description provided.",
                      'start': { 'date': due_date }, # Format: 'YYYY-MM-DD'
                      'end': { 'date': due_date },
                    }
                    # Call the function from google_calendar.py
                    pushOutgoingEvents(event_data)

                if current_db_id and task.get("subtasks"):
                    process_task_list(task["subtasks"], current_db_id)

        cursor.execute("SELECT item_id FROM work_items WHERE project_id = ? AND parent_item_id IS NULL", (project_id,))
        root_item = cursor.fetchone()
        root_item_id = root_item['item_id'] if root_item else None

        process_task_list(tasks_data, root_item_id)

        conn.commit()
        return jsonify({"message": "Tasks saved successfully!", "new_ids_map": id_map}), 200

    except Exception as e:
        conn.rollback()
        print(f"Error saving tasks: {e}")
        traceback.print_exc()
        return jsonify({"error": "Internal server error", "details": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)