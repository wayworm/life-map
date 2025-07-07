from datetime import date
from dateutil.relativedelta import relativedelta
from flask import Flask, flash, redirect, render_template, request, session, g, jsonify
from flask_session import Session
from functools import wraps
import traceback
import sqlite3
from werkzeug.security import check_password_hash, generate_password_hash


# TODO: Add a maximum value of 6 layers of subtasks. Present a message to screen if they try to go deeper.
# TODO: Link to Google Calendar.
# TODO: Add functionality to sort hours assigned to task
# TODO: Logic to disallow a subtask to have more hours attributed to it than it's parent task.
# TODO: Add functionality to reorder the tasks by drag and drop.
# TODO: Make nav bar stick to top of page when scrolling down.
# TODO: Project pages due date --> years, months, weeks, days dependings on timescale 


# Configure application
app = Flask(__name__)

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)


def error_page(message, code=400):
    """Render error page to user."""
    return render_template("error_page.html", code=code, message=message), code

def get_db():
    if 'lifemap_db' not in g:
        g.lifemap_db = sqlite3.connect("LifeMap.db")
        g.lifemap_db.row_factory = sqlite3.Row
    return g.lifemap_db


def login_required(f):
    """
    Decorate routes to require login.
    https://flask.palletsprojects.com/en/latest/patterns/viewdecorators/
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get("user_id") is None:
            return redirect("/login")
        return f(*args, **kwargs)
    return decorated_function


def build_task_tree(tasks_flat_list):
    """
    Builds a hierarchical tree of tasks and subtasks from a flat list,
    and calculates rolled-up planned_hours.

    Args:
        tasks_flat_list (list of dict or sqlite3.Row): A list of task records.

    Returns:
        list: A list of top-level task dictionaries, each potentially containing
              a 'subtasks' key which is a list of subtask dictionaries.
              Each task dictionary will have a 'calculated_planned_hours' field.
    """
    task_map = {}
    for task_row in tasks_flat_list:
        task_dict = dict(task_row)
        task_dict['id'] = task_dict['item_id']
        task_dict['parent_id'] = task_dict['parent_item_id'] # Use parent_id for consistency
        task_dict['completed'] = bool(task_dict['is_completed'])
        task_dict['subtasks'] = [] # Initialize subtasks list
        # Store actual planned_hours from DB for leaf nodes
        task_dict['individual_planned_hours'] = task_dict['planned_hours']

        task_map[task_dict['id']] = task_dict

    tree = []

    # Assign children to parents and identify top-level tasks
    for taskid, task in task_map.items():
        if task['parent_id'] is not None:
            parent_id = task['parent_id']
            if parent_id in task_map:
                task_map[parent_id]['subtasks'].append(task)
        else:
            tree.append(task)

    # Recursive function to calculate rolled-up planned hours
    def calculate_rolled_up_hours(task):
        total_hours = 0.0
        
        # If task has subtasks, sum their rolled-up hours
        if task['subtasks']:
            for subtask in task['subtasks']:
                total_hours += calculate_rolled_up_hours(subtask)
        
        # Add its own individual planned hours if it has any and is not a parent being summed
        # This logic ensures leaf nodes contribute their own hours, and parents sum their children's.
        # If a parent task itself has individual_planned_hours, it can represent overhead not broken down further.
        # Adjust this logic based on whether you want a parent's 'individual_planned_hours' to add to its children's sum.
        # Common pattern: If a task has subtasks, its planned_hours are *only* the sum of children.
        # If no subtasks, it's its own individual_planned_hours.
        if not task['subtasks'] and task['individual_planned_hours'] is not None:
             total_hours += task['individual_planned_hours']
        elif task['subtasks'] and task['individual_planned_hours'] is not None:
            # If a parent also has individual planned hours, you might want to add them as overhead
            # Or you might want to ignore them entirely, assuming the parent's hours are purely derived.
            # For now, let's assume if it has subtasks, its own planned_hours are rolled up, so we don't add individual
            # planned_hours if it has subtasks. If you want overhead, add it here.
            pass


        task['calculated_planned_hours'] = total_hours
        
        # To display its own input value in the frontend, keep its 'planned_hours' attribute as is.
        # The frontend will use 'task.planned_hours' for the input field, and 'task.calculated_planned_hours' for display if needed.
        return total_hours

    # Sort tasks and then calculate rolled-up hours (needs to be bottom-up)
    def sort_and_calculate_recursive(tasks_list):
        # Sort tasks by their 'display_order' if available, otherwise by 'id'
        tasks_list.sort(
            key=lambda t: t.get(
                'display_order',
                t['id']) if t.get('display_order') is not None else t['id'])
        
        # Calculate rolled-up hours after sorting, to ensure children are processed first
        for t in tasks_list:
            if t['subtasks']:
                sort_and_calculate_recursive(t['subtasks'])
            calculate_rolled_up_hours(t) # Calculate after subtasks are processed

    sort_and_calculate_recursive(tree)
    
    # After all calculations, ensure the top-level project task also has its calculated hours
    # The 'tree' only contains the project task itself (level 0).
    # Its 'calculated_planned_hours' will be the sum of its direct children (level 1 tasks)
    # and their descendants.
    
    return tree


def get_username(user_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""SELECT username FROM users WHERE user_id = ?""", (user_id,))
    username_row = cursor.fetchone()
    # No need to close_db here, as it's handled by @app.teardown_appcontext
    return username_row[0] if username_row else None # Return None if user not found

def format_date_difference(target_date_str: str) -> str:
    # Parse input
    target_date = date.fromisoformat(target_date_str)
    today = date.today()
    delta = relativedelta(target_date, today)

    if target_date < today:
        return "Date has passed"

    parts = []
    if delta.years:
        parts.append(f"{delta.years} year{'s' if delta.years != 1 else ''}")
    if delta.months:
        parts.append(f"{delta.months} month{'s' if delta.months != 1 else ''}")
    if delta.days:
        parts.append(f"{delta.days} day{'s' if delta.days != 1 else ''}")

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

            # When creating the main project work_item, planned_hours should be NULL
            # as it will be calculated from its children.
            cursor.execute("""INSERT INTO work_items
                               (project_id, parent_item_id, name, description, planned_hours)
                               VALUES (?, ?, ?, ?, ?)""", (project_id, None, title, description, None)) # Set planned_hours to NULL for new projects

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
            
            # Update the corresponding top-level work_item's name and description.
            # Crucially, DO NOT touch planned_hours here, as it's rolled-up.
            cursor.execute("""
                UPDATE work_items
                SET name = ?, description = ?
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
    """Display tasks for a specific project."""
    user_id = session["user_id"]
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""SELECT name, description FROM projects WHERE user_id = ? AND project_id = ?""", (user_id, project_id))
    project_details = cursor.fetchone()

    if project_details is None:
        cursor.execute("SELECT 1 FROM projects WHERE project_id = ?", (project_id,))
        if cursor.fetchone():
            return error_page("You are not authorized to view this project.", 403)
        else:
            return error_page("Project not found.", 404)

    project_name = project_details["name"]

    cursor.execute("""SELECT * FROM work_items WHERE project_id = ?""", (project_id,))
    tasks_flat_list = cursor.fetchall()
    
    # Build the tree and calculate rolled-up hours before sending to template
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
    """Show all user projects."""
    if request.method == "GET":
        conn = get_db()
        cursor = conn.cursor()
        user_id = session["user_id"]

        cursor.execute("""SELECT * FROM projects WHERE user_id = ? ORDER BY end_date ASC""", (user_id,))
        rows = cursor.fetchall()
        rows_list = []
        for row in rows:
            rows_list.append(dict(row))
        for row in rows_list:
            row["readable_due_date"] = format_date_difference(row["end_date"])

        # No direct `this_week` usage in template, but calculated here
        this_week = [f"{i} day{'s' if i != 1 else ''}" for i in range(7)]

        return render_template(
            "projects.html",
            projects=rows_list,
            username=get_username(user_id),
            this_week=this_week)
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

        # If work_items has ON DELETE CASCADE, this single delete is enough.
        # Otherwise, you'd need to DELETE FROM work_items WHERE project_id = ? first.
        cursor.execute("DELETE FROM projects WHERE project_id = ?", (project_id,))
        conn.commit()
        flash("Project deleted successfully!", "success")
    except Exception as e:
        conn.rollback()
        print(f"Error deleting project: {e}")
        flash(f"An error occurred while deleting the project: {e}", "danger")
    return redirect("/projects")


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
        deleted_task_ids = data.get("deleted_task_ids", [])

        # Validate project ownership
        cursor.execute(
            "SELECT 1 FROM projects WHERE user_id = ? AND project_id = ?",
            (user_id, project_id)
        )
        if not cursor.fetchone():
            return jsonify({"error": "Project not found or not owned by user."}), 403

        # 1. Handle Deletions
        if deleted_task_ids:
            clean_deleted_ids = []
            for task_id in deleted_task_ids:
                if isinstance(task_id, str) and task_id.isdigit():
                    clean_deleted_ids.append(int(task_id))

            if clean_deleted_ids:
                placeholders = ','.join(['?'] * len(clean_deleted_ids))
                cursor.execute(f"""
                    DELETE FROM work_items
                    WHERE item_id IN ({placeholders}) AND project_id = ?
                """, clean_deleted_ids + [project_id])
                
                print(f"Debug: Deleted {cursor.rowcount} tasks with IDs: {clean_deleted_ids}")
            else:
                print(f"INFO: No valid numeric IDs found for deletion in {deleted_task_ids}")
        conn.commit()

        # 2. Process tasks for inserts/updates
        id_map = {}

        def process_task_list(task_list, parent_db_id=None):
            for task in task_list:
                client_id = task["id"]
                name = task["name"]
                description = task.get("description")
                
                due_date_str = task.get("due_date")
                due_date = due_date_str if due_date_str else None
                
                completed = task.get("completed", False)
                priority = task.get("priority", 0) # Default if not provided
                status = task.get("status", "To Do") # Default if not provided
                assigned_to_user_id = task.get("assigned_to_user_id") # Keep None if not set
                display_order = task.get("display_order", 0) # Default if not provided
                
                # Planned hours will only be stored for LEAF tasks (tasks that have no subtasks)
                # or tasks that are explicitly input by the user AND have no subtasks.
                # For parent tasks, it should be NULL in DB and calculated on retrieval.
                planned_hours_input = task.get("planned_hours")
                
                # Check if this task is a LEAF NODE on the frontend (has no subtasks)
                # and if planned_hours was provided from its input field.
                # If it has subtasks on the frontend, its planned_hours should be NULL in DB
                # as it will be derived.
                planned_hours_to_save = None
                if not task.get("subtasks") and planned_hours_input not in ['', None]:
                    try:
                        planned_hours_to_save = float(planned_hours_input)
                    except ValueError:
                        print(f"Warning: Invalid planned_hours value '{planned_hours_input}' for task '{name}'. Setting to NULL.")
                        planned_hours_to_save = None


                print(f"Debug: Processing task - client_id: '{client_id}', name: '{name}', parent_db_id: {parent_db_id}")
                print(f"Values: Desc='{description}', Due='{due_date}', Comp='{completed}', Prio='{priority}', Status='{status}', Assigned='{assigned_to_user_id}', Display='{display_order}', Planned_to_Save='{planned_hours_to_save}'")


                current_db_id = None

                if isinstance(client_id, str) and client_id.startswith("new-"):
                    cursor.execute("""
                        INSERT INTO work_items
                        (project_id, parent_item_id, name, description, due_date, is_completed, priority, status, assigned_to_user_id, display_order, planned_hours)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (project_id, parent_db_id, name, description, due_date, completed, priority, status, assigned_to_user_id, display_order, planned_hours_to_save))
                    
                    new_db_id = cursor.lastrowid
                    id_map[client_id] = new_db_id
                    current_db_id = new_db_id
                    print(f"Debug: Inserted new task. Client ID: {client_id}, New DB ID: {new_db_id}")
                
                elif isinstance(client_id, (int, str)) and str(client_id).isdigit():
                    try:
                        current_db_id = int(client_id)
                        cursor.execute("""
                            UPDATE work_items
                            SET name = ?, description = ?, due_date = ?, is_completed = ?,
                                priority = ?, status = ?, assigned_to_user_id = ?, display_order = ?,
                                parent_item_id = ?, planned_hours = ?
                            WHERE item_id = ? AND project_id = ?
                        """, (name, description, due_date, completed, priority, status, assigned_to_user_id,
                              display_order, parent_db_id, planned_hours_to_save, current_db_id, project_id))

                        print(f"Debug: Updated existing task. DB ID: {current_db_id}, Parent ID: {parent_db_id}")
                    except ValueError:
                        print(f"ERROR: Could not convert client_id '{client_id}' to int. Skipping update for this task.")
                        continue
                else:
                    print(f"WARNING: Skipping task '{name}' with invalid client_id '{client_id}' (expected existing numeric ID or 'new-' prefix).")
                    continue

                if current_db_id is not None and task.get("subtasks"):
                    # Pass the newly obtained DB ID to recursive call for subtasks
                    process_task_list(task["subtasks"], current_db_id)

        # Start processing the top-level tasks
        # The first item in tasks_data is always the project's own work_item, which has parent_id=NULL.
        # Its planned_hours will be NULL in the DB and rolled up on retrieval.
        process_task_list(tasks_data)

        # Update top-level work_item (project task) details if they've changed
        # This now correctly uses project_id as a parameter for subqueries as well.
        cursor.execute("""
            UPDATE work_items
            SET
                name = (SELECT name FROM projects WHERE project_id = ?),
                description = (SELECT description FROM projects WHERE project_id = ?)
            WHERE parent_item_id IS NULL AND project_id = ?
        """, (project_id, project_id, project_id))

        conn.commit()
        return jsonify({"message": "Tasks saved successfully!", "new_ids_map": id_map}), 200

    except Exception as e:
        conn.rollback()
        print(f"Error saving tasks: {e}")
        traceback.print_exc()
        return jsonify({"error": "Internal server error", "details": str(e)}), 500


if __name__ == '__main__':
    app.run(debug=True)