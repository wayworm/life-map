from flask import Flask, flash, redirect, render_template, request, jsonify
from flask_session import Session
import traceback
from werkzeug.security import check_password_hash, generate_password_hash
from google_calendar import *
from help import *
import logging



# NICE TO HAVE Changes
# TODO: Let text area for a task grow and push everything below it downward.
# TODO: Add sort buttons next to the column headers on the projects page *maybe*. Might be a better way of doing this.
# TODO: Add a line connecting the parent task to all its children. e.g. :
# parent
#      |
#      L Child 1
#      |     |
#      |     L Child 1's child
#      |
#      L Child 2

# DID IT:
#   DONE: BUGFIX: When adding new tasks to a project, the top level task does not get assigned the correct parent ID.
#   DONE: Fix the broken task saving function...
#   DONE: added new test user
#   DONE: Added shadow to navbar text items, so they are distinguished from background.
#   DONE: fix this bug: level 1 tasks' hour tracking are read only even when they have no subtasks.
#   DONE: fix the "Description" text going over the input.
#   DONE: Fix "A subtask's due date cannot be later than its parent's due date" error when same level task has later due date.
#   DONE: Fix subtask duplication bug.
#   DONE: fix bug: When changing the due date of a task, the original google calendar task is not deleted.
#   DONE: Link to Google Calendar.
#   DONE: Delete all related google events when deleting a project.

# Configure application
app = Flask(__name__)

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)


def task_to_dict(row):
    return {
        "item_id": row[0],
        "name": row[1],
        "description": row[2],
        "due_date": row[3],
        "is_completed": row[4],
        "is_minimized": row[5],
        "display_order": row[6],
        "planned_hours": row[7],
        "parent_item_id": row[8],
        "google_calendar_event_id": row[9],
    }


def log_calls(func):
    def wrapper(*args, **kwargs):
        logging.info(f"Calling {func.__name__}")
        return func(*args, **kwargs)

    return wrapper


def error_page(message, code=400):
    """Render error page to user."""
    return render_template("error_page.html", code=code, message=message), code


@app.teardown_appcontext
def close_db(e=None):
    lifemap_db = g.pop("lifemap_db", None)
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
        cursor.execute(
            """UPDATE users SET username = ? WHERE user_id = ?""",
            (new_username, user_id),
        )
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
            return error_page(
                "New password cannot be the same as current password.", 400
            )
        new_hashed_password = generate_password_hash(
            new_password, method="scrypt", salt_length=16
        )
        try:
            cursor.execute(
                """UPDATE users SET password_hash = ? WHERE user_id = ?""",
                (new_hashed_password, user_id),
            )
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
        cursor.execute(
            """SELECT * FROM users WHERE username = ? OR email = ? LIMIT 1""",
            (login_input, login_input),
        )
        row = cursor.fetchone()

        if not row or not check_password_hash(row["password_hash"], password):
            lowered = login_input.lower()
            cursor.execute(
                """SELECT * FROM users WHERE email = ? LIMIT 1""", (lowered,)
            )
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

        if not username:
            return error_page("must provide username", 400)
        elif not password:
            return error_page("must provide password", 400)
        elif not confirmation:
            return error_page("must confirm password", 400)
        elif password != confirmation:
            return error_page("Passwords don't match", 400)
        if len(password) < 8:
            return error_page("Password must be at least 8 characters long.")
        if not any(char.isdigit() for char in password):
            return error_page("Password must contain at least one digit.")
        if not any(char.isupper() for char in password):
            return error_page("Password must contain at least one uppercase letter.")
        if not any(char.islower() for char in password):
            return error_page("Password must contain at least one lowercase letter.")

        conn = get_db()
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT user_id FROM users WHERE username = ?", (username,))
            if cursor.fetchone():
                return error_page("Username already taken.", 400)
            hashed_password = generate_password_hash(
                password, method="scrypt", salt_length=16
            )
            cursor.execute(
                """INSERT INTO users (username, email, password_hash) VALUES (?,?,?) """,
                (username, email, hashed_password),
            )
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

        if not title:
            return error_page("No Title entered.", 400)
        if not description:
            return error_page("No description entered.", 400)

        conn = get_db()
        cursor = conn.cursor()
        try:
            cursor.execute(
                """SELECT project_id FROM projects WHERE user_id = ? AND name = ?""",
                (user_id, title),
            )
            if cursor.fetchone():
                return error_page("You already have a project with this name.", 400)

            cursor.execute(
                """INSERT INTO projects (user_id, name, description, end_date, start_date) VALUES (?, ?, ?, ?, ?)""",
                (user_id, title, description, due_date, start_date),
            )
            project_id = cursor.lastrowid

            cursor.execute(
                """INSERT INTO work_items (project_id, parent_item_id, name, description, planned_hours) VALUES (?, ?, ?, ?, ?)""",
                (project_id, None, title, description, None),
            )

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
        cursor.execute(
            """SELECT name, description FROM projects WHERE user_id = ? AND project_id = ?""",
            (user_id, project_id),
        )
        project = cursor.fetchone()
        if project is None:
            return error_page(
                "Project not found or you don't have permission to edit.", 404
            )
        return render_template(
            "editProject.html",
            current_project=dict(project),
            project_id=project_id,
            username=get_username(user_id),
        )

    elif request.method == "POST":
        new_title = request.form.get("projectTitle")
        new_description = request.form.get("projectDescription")

        if not new_title:
            return (
                jsonify(
                    {"success": False, "error": "New project title cannot be empty."}
                ),
                400,
            )

        try:
            cursor.execute(
                "SELECT 1 FROM projects WHERE user_id = ? AND project_id = ?",
                (user_id, project_id),
            )
            if not cursor.fetchone():
                return (
                    jsonify(
                        {
                            "success": False,
                            "error": "Project not found or not authorized.",
                        }
                    ),
                    403,
                )

            cursor.execute(
                """UPDATE projects SET name = ?, description = ? WHERE project_id = ?""",
                (new_title, new_description, project_id),
            )

            cursor.execute(
                """
                UPDATE work_items SET name = ?, description = ?
                WHERE project_id = ? AND parent_item_id IS NULL
            """,
                (new_title, new_description, project_id),
            )

            conn.commit()
            flash("Project updated successfully!", "success")
            return redirect("/projects")
        except Exception as e:
            traceback.print_exc()
            conn.rollback()
            return (
                jsonify({"success": False, "error": f"Internal server error: {e}"}),
                500,
            )


@app.route("/details/<int:project_id>")
@login_required
def tasks(project_id):

    user_id = session["user_id"]
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        """SELECT name, description FROM projects WHERE user_id = ? AND project_id = ?""",
        (user_id, project_id),
    )

    project_details = cursor.fetchone()

    if project_details is None:
        return error_page("Project not found or you are not authorized.", 404)

    project_name = project_details["name"]

    cursor.execute("""SELECT * FROM work_items WHERE project_id = ?""", (project_id,))

    tasks_flat_list = cursor.fetchall()

    tree = build_task_tree(tasks_flat_list)

    return render_template(
        "tasks.html",
        tasks=tree,
        project_id=project_id,
        project_name=project_name,
        username=get_username(user_id),
        project_details=project_details,
    )


@app.route("/projects/<int:project_id>/delete", methods=["POST"])
@login_required
def delete_project(project_id):
    """Deletes a project and all its associated work items and Google Calendar events."""
    user_id = session["user_id"]
    conn = get_db()
    cursor = conn.cursor()

    try:
        # Verify the project belongs to the current user
        cursor.execute(
            "SELECT user_id FROM projects WHERE project_id = ?", (project_id,)
        )
        project_owner = cursor.fetchone()

        if not project_owner or project_owner["user_id"] != user_id:
            flash("Unauthorized or project not found.", "error")
            return redirect("/projects")

        # --- NEW: Delete Google Calendar Events ---
        # 1. Find all event IDs for this project's tasks before deleting them.
        cursor.execute(
            "SELECT google_calendar_event_id FROM work_items WHERE project_id = ? AND google_calendar_event_id IS NOT NULL",
            (project_id,),
        )
        event_ids_to_delete = [
            row["google_calendar_event_id"] for row in cursor.fetchall()
        ]

        # 2. Loop through the IDs and delete each event from Google Calendar.
        for event_id in event_ids_to_delete:
            try:
                delete_google_event(event_id)
            except Exception as e:
                # Log the error but continue, so the project still gets deleted from your app
                print(
                    f"Warning: Failed to delete Google Calendar event {event_id}: {e}"
                )
        # --- END NEW LOGIC ---

        # Delete all data related to project from your database
        cursor.execute("DELETE FROM work_items WHERE project_id = ?", (project_id,))
        cursor.execute("DELETE FROM projects WHERE project_id = ?", (project_id,))

        # Commit the transaction
        conn.commit()
        flash("Project deleted successfully!", "success")
        return redirect("/projects")

    except sqlite3.Error as e:
        conn.rollback()
        print(f"Database error during project deletion: {e}")
        flash(
            "An error occurred while deleting the project. Please try again.", "error"
        )
        return redirect(f"/projects/{project_id}/edit")


@app.route("/calendar")
@login_required
def calendar():
    user_id = session["user_id"]
    conn = get_db()
    cursor = conn.cursor()

    # Fetch tasks with due dates for the current user
    # We select google_calendar_event_id to check if an event already exists
    cursor.execute(
        """
        SELECT name, description, due_date, google_calendar_event_id
        FROM work_items
        WHERE project_id IN (SELECT project_id FROM projects WHERE user_id = ?)
        AND due_date IS NOT NULL
        ORDER BY due_date
    """,
        (user_id,),
    )

    tasks_with_due_dates = cursor.fetchall()

    # SELECT * FROM work_items WHERE project_id = 20 AND due_date IS NOT NULL ORDER BY due_date;

    events_for_calendar = []
    for task in tasks_with_due_dates:
        # FullCalendar expects events in a specific format.
        # title is the event's title
        # start is the event's start date/time
        # end is the event's end date/time (optional, if it's an all-day event, it should be the day *after* the event)
        # We'll use the due_date for both start and end for all-day events.
        events_for_calendar.append(
            {
                "title": task["name"],
                "start": task["due_date"],
                "end": task[
                    "due_date"
                ],  # For all-day events, FullCalendar treats 'end' as exclusive. If your event is on '2025-07-15', setting end to '2025-07-15' will show it as one day. If you want it to span the entire day and appear on the 15th, you typically just need the 'start' date. For simplicity with "due dates" being single days, setting start and end to the same date is common for all-day events.
                "description": task["description"],
                "id": task[
                    "google_calendar_event_id"
                ],  # Use the Google Calendar event ID if available
            }
        )

    return render_template(
        "calendar.html", events=events_for_calendar, username=get_username(user_id)
    )


@app.route("/projects", methods=["GET", "POST"])
@login_required
def projects_list():
    if request.method == "GET":
        conn = get_db()
        cursor = conn.cursor()
        user_id = session["user_id"]

        cursor.execute(
            """SELECT * FROM projects WHERE user_id = ? ORDER BY end_date ASC""",
            (user_id,),
        )
        rows = [dict(row) for row in cursor.fetchall()]
        for row in rows:
            row["readable_due_date"] = format_date_difference(row["end_date"])

        return render_template(
            "projects.html", projects=rows, username=get_username(user_id)
        )
    else:
        return error_page("Request Error, Only GET requests accepted.", 403)


@app.route("/save-tasks", methods=["POST"])
@login_required
@log_calls
def save_tasks():
    user_id = session["user_id"]
    conn = get_db()
    cursor = conn.cursor()

    try:
        # Get data from the POST request
        data = request.get_json()
        project_id = data.get("project_id")
        tasks_data = data.get("tasks", [])
        deleted_item_ids = data.get("deleted_item_ids", [])

        cursor.execute(
            "SELECT item_id, google_calendar_event_id FROM work_items WHERE project_id = ?",
            (project_id,),
        )

        existing_google_events = {
            row["item_id"]: row["google_calendar_event_id"] for row in cursor.fetchall()
        }

        # Verify the user owns the project
        cursor.execute(
            "SELECT 1 FROM projects WHERE user_id = ? AND project_id = ?",
            (user_id, project_id),
        )
        if not cursor.fetchone():
            return jsonify({"error": "Project not found or not owned by user."}), 403

        # Handle any tasks marked for deletion
        if deleted_item_ids:
            clean_ids = [int(i) for i in deleted_item_ids if str(i).isdigit()]
            if clean_ids:
                placeholders = ",".join(["?"] * len(clean_ids))

                cursor.execute(
                    f"SELECT item_id, google_calendar_event_id FROM work_items WHERE item_id IN ({placeholders})",
                    clean_ids,
                )
                items_to_delete = cursor.fetchall()

                for item in items_to_delete:
                    if item["google_calendar_event_id"]:
                        delete_google_event(item["google_calendar_event_id"])

                # Finally, delete the tasks from the database
                cursor.execute(
                    f"DELETE FROM work_items WHERE item_id IN ({placeholders}) AND project_id = ?",
                    clean_ids + [project_id],
                )

        # Define the recursive function to process all incoming tasks
        id_map = {}

        # Start the process with the top-level tasks from the request
        process_task_list(
            tasks_data, cursor, id_map, project_id, existing_google_events
        )

        conn.commit()
        return (
            jsonify({"message": "Tasks saved successfully!", "new_ids_map": id_map}),
            200,
        )

    except Exception as e:

        conn.rollback()
        traceback.print_exc()

        return jsonify({"error": "Internal server error", "details": str(e)}), 500


if __name__ == "__main__":
    app.run(debug=True)
