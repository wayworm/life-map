from flask import Flask, flash, redirect, render_template, request, session, g, jsonify 
from flask_session import Session
from functools import wraps
import traceback
import sqlite3
from werkzeug.security import check_password_hash, generate_password_hash


# Configure application
app = Flask(__name__)

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

def error_page(message, code=400):
    """Render error page to user."""

    return render_template("error_page.html", code=code, message=message), code

# Configure database
def get_db():
    if 'lifemap_db' not in g: # Use a different key for LifeMap DB
        g.lifemap_db = sqlite3.connect("LifeMap.db")
        g.lifemap_db.row_factory = sqlite3.Row # This will allow you to access columns by name
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
    Builds a hierarchical tree of tasks and subtasks from a flat list.

    Args:
        tasks_flat_list (list of dict or sqlite3.Row): A list of task records,
            where each record is expected to have 'item_id', 'parent_item_id',
            'name', 'description', 'due_date', 'is_completed', 'priority',
            'status', 'assigned_to_user_id', 'display_order',
            'created_at', and 'updated_at' keys/attributes.

    Returns:
        list: A list of top-level task dictionaries, each potentially containing
              a 'subtasks' key which is a list of subtask dictionaries.
    """
    # Create a dictionary to quickly access tasks by their item_id
    # Ensure all original fields are copied into the dictionary,
    # as the Jinja template expects 'id' and 'parent_item_id' for display.
    # Map 'item_id' to 'id' and 'is_completed' to 'completed' boolean for consistency
    # with the Jinja template and JavaScript expectations.
    task_map = {}
    for task_row in tasks_flat_list:
        task_dict = dict(task_row) # Convert sqlite3.Row to dict
        task_dict['id'] = task_dict['item_id'] # Map item_id to 'id' for Jinja/JS
        task_dict['parent_item_id'] = task_dict['parent_item_id'] # Keep parent_item_id as is
        task_dict['completed'] = bool(task_dict['is_completed']) # Map is_completed to 'completed' boolean
        task_map[task_dict['id']] = task_dict

    tree = [] # This will hold the top-level tasks

    # Iterate over all tasks to initialize subtasks list and build hierarchy
    for taskid, task in task_map.items():
        # Ensure 'subtasks' list exists for all tasks, even if empty
        task['subtasks'] = []   

        # Check if subtask
        if task['parent_item_id'] is not None:
            parent_id = task['parent_item_id']

            # If the parent exists in our map, add this task to its subtasks
            if parent_id in task_map:
                task_map[parent_id]['subtasks'].append(task)

        else:
            # It's a top-level task
            tree.append(task)

    # Sort top-level tasks and their subtasks recursively
    # Sorting by 'item_id' (mapped to 'id') ensures consistent order.
    def sort_tasks_recursive(tasks_list):
        # Sort tasks by their 'display_order' if available, otherwise by 'id'
        # Assume 'display_order' might be a numeric field
        tasks_list.sort(key=lambda t: t.get('display_order', t['id']) if t.get('display_order') is not None else t['id'])
        for t in tasks_list:
            if t['subtasks']:
                sort_tasks_recursive(t['subtasks'])

    sort_tasks_recursive(tree) # Sort the entire tree

    return tree


def get_username(user_id):
    conn = get_db()
    conn.execute("PRAGMA foreign_keys = ON")
    cursor = conn.cursor()

    cursor.execute("""SELECT username
                          FROM users
                          WHERE user_id = ?""", (user_id,)) 
    
    username = cursor.fetchone()
    close_db()

    return username[0]

@app.teardown_appcontext
def close_db(e=None):
    # Close lifemap_db if it exists
    lifemap_db = g.pop('lifemap_db', None)
    if lifemap_db is not None:
        lifemap_db.close()


@app.after_request
def after_request(response):
    """Ensure responses aren't cached"""
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
    """Modify account settings"""

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
    conn.execute("PRAGMA foreign_keys = ON")
    cursor = conn.cursor()

    cursor.execute("""UPDATE users 
                        SET username = ? 
                        WHERE user_id = ?""", (new_username, user_id))
    
    conn.commit()
    return redirect("/")


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
    conn.execute("PRAGMA foreign_keys = ON")
    cursor = conn.cursor()

    cursor.execute("""SELECT password_hash 
                        FROM users 
                        WHERE user_id = ?""", (user_id,))

    user_hash_record = cursor.fetchone()
    if user_hash_record is None:
        return error_page("User not found.", 404) # Should not happen if login_required works

    stored_hash = user_hash_record["password_hash"]

    if check_password_hash(stored_hash, current_password):

        if check_password_hash(stored_hash, new_password):
            return error_page("New password cannot be the same as current password.", 400)
        
        # Generate new hash for the new password
        new_hashed_password = generate_password_hash(new_password, method='scrypt', salt_length=16)

        cursor.execute("""UPDATE users 
                            SET password_hash = ? 
                            WHERE user_id = ?""", (new_hashed_password, user_id))

        conn.commit() 
        flash("Password changed successfully!") # Flash message for success
        return redirect("/")

    else:
        return error_page("Incorrect current password.")



@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":
        # Ensure username was submitted
        if not request.form.get("username"):
            return error_page("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return error_page("must provide password", 403)

        conn = get_db() # Using LifeMap.db for login
        conn.execute("PRAGMA foreign_keys = ON")
        cursor = conn.cursor()

        username_to_query = request.form.get("username")
 

        cursor.execute("""SELECT *
                         FROM users
                         WHERE username = ?""", (username_to_query,))

        rows = cursor.fetchall()

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(
            rows[0]["password_hash"], request.form.get("password")
        ):
            return error_page("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["user_id"] # Ensure this matches your DB column name (e.g., 'id' or 'user_id')
    
        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        email = request.form.get("email") # Email is optional if not strictly required by DB
        confirmation = request.form.get("confirmation")
        
        # Basic input validation
        if not username:
            return error_page("must provide username", 400)
        elif not password:
            return error_page("must provide password", 400)
        elif not confirmation:
            return error_page("must confirm password", 400)
        elif password != confirmation:
            return error_page("Passwords don't match", 400)
        
        # Password strength validation (optional, but good practice)
        if len(password) < 8:
            return error_page("Password must be at least 8 characters long.")
        if not any(char.isdigit() for char in password):
            return error_page("Password must contain at least one digit.")
        if not any(char.isupper() for char in password):
            return error_page("Password must contain at least one uppercase letter.")
        if not any(char.islower() for char in password):
            return error_page("Password must contain at least one lowercase letter.")


        conn = get_db() # Using LifeMap.db for user registration
        conn.execute("PRAGMA foreign_keys = ON")
        cursor = conn.cursor()

        try:
            # Check if username already exists
            cursor.execute("SELECT user_id FROM users WHERE username = ?", (username,))
            if cursor.fetchone():
                return error_page("Username already taken.", 400)

            # Hash the password
            hashed_password = generate_password_hash(password, method='scrypt', salt_length=16)
            
            # Insert new user into the database
            cursor.execute("""INSERT INTO users (username, email, password_hash)
                             VALUES (?,?,?) """, (username, email, hashed_password))
            
            conn.commit() 
            flash("Registered successfully! Please log in.") # Flash message for success
            return redirect("/login") # Redirect to login page after registration

        except Exception as e:
            traceback.print_exc() # Print full traceback for debugging
            conn.rollback() # Rollback transaction in case of error
            return error_page(f"Registration error: {e}") # Provide more specific error info


    elif request.method == "GET":
        return render_template("register.html")

    else:
        return error_page("Registration Error") # This part might not be reachable if methods are GET/POST only


@app.route("/newProject", methods=["GET","POST"])
@login_required
def newProject():
    """Add new Project to database"""
    
    user_id = session["user_id"]

    if request.method == "POST":
        title = request.form.get("title")
        description = request.form.get("description")
        start_date = request.form.get("start_date")
        due_date = request.form.get("end_date")
        user_id = session["user_id"] 

        if not title: # More Pythonic check for empty string
            return error_page("No Title entered.", 400)

        if not description: # More Pythonic check for empty string
            return error_page("No description entered.", 400)


        conn = get_db()
        conn.execute("PRAGMA foreign_keys = ON")
        cursor = conn.cursor()

        try:

            cursor.execute("""SELECT project_id FROM projects WHERE user_id = ? AND name = ?""", (user_id, title))
            if cursor.fetchone():
                return error_page("You already have a project with this name.", 400)

            # Create new project in projects table
            
            cursor.execute("""INSERT INTO projects
                            (user_id, name, description, end_date, start_date)
                            VALUES (?, ?, ?, ?, ?)""", (user_id, title, description, due_date, start_date))

            # Get the project_id of the newly inserted project
            project_id = cursor.lastrowid 

            # Insert the main project as a top-level work_item associated with the project
            cursor.execute("""INSERT INTO work_items
                             (project_id, parent_item_id, name, description)
                             VALUES (?, ?, ?, ?)""", (project_id, None, title, description))

            conn.commit() 
            flash(f"Project '{title}' created successfully!") # Flash message for success
            return redirect("/projects") # Redirect to projects list

        except Exception as e:
            traceback.print_exc()
            conn.rollback()
            return error_page(f"Error creating project: {e}")

    else:
        return render_template("newProject.html", username=get_username(user_id))
    

@app.route("/projects/<int:project_id>/edit", methods=["GET","POST"]) # Renamed route for clarity
@login_required
def edit_project(project_id):
    """Edit project title and potentially other details."""
    user_id = session["user_id"]
    conn = get_db()
    conn.execute("PRAGMA foreign_keys = ON")
    cursor = conn.cursor()

    if request.method == "GET":
        cursor.execute("""SELECT name, description
                         FROM projects
                         WHERE user_id = ? AND project_id = ?""", (user_id, project_id))
        
        project = cursor.fetchone()

        if project is None:
            return error_page("Project not found or you don't have permission to edit.", 404)

        return render_template("editProject.html", current_project=dict(project), project_id=project_id, username=get_username(user_id)) # Pass project_id for JS

    elif request.method == "POST":
        new_title = request.form.get("projectTitle") # Get new title from form
        # new_description = request.form.get("projectDescription") # Add if you expand the form

        if not new_title:
            return jsonify({"success": False, "error": "New project title cannot be empty."}), 400

        try:
            # Verify project ownership before updating
            cursor.execute("SELECT 1 FROM projects WHERE user_id = ? AND project_id = ?", (user_id, project_id))
            if not cursor.fetchone():
                return jsonify({"success": False, "error": "Project not found or not authorized."}), 403

            # Update the project title
            cursor.execute("""UPDATE projects 
                             SET name = ? 
                             WHERE project_id = ?""", (new_title, project_id)) # Add new_description if needed

            # Also update the corresponding top-level work_item's name if it represents the project itself
            # Assuming the main project work_item has parent_item_id IS NULL and name matches project name initially
            cursor.execute("""UPDATE work_items
                             SET name = ?
                             WHERE project_id = ? AND parent_item_id IS NULL
                             AND name = (SELECT name FROM projects WHERE project_id = ?)""", # Only update if it's the original project name
                             (new_title, project_id, project_id))


            conn.commit() 
            return redirect("/")

        except Exception as e:
            traceback.print_exc()
            conn.rollback()
            return jsonify({"success": False, "error": f"Internal server error: {e}"}), 500
    
    return error_page("Method not allowed", 405) # Fallback for unsupported methods


@app.route("/details/<int:project_id>")
@login_required
def tasks(project_id):
    """Display tasks for a specific project."""

    user_id = session["user_id"]
    conn = get_db()
    conn.execute("PRAGMA foreign_keys = ON")
    cursor = conn.cursor()

    # Fetch project details and verify ownership
    cursor.execute("""SELECT name, description
                     FROM projects
                     WHERE user_id = ? AND project_id = ?""", (user_id, project_id))
    
    project_details = cursor.fetchone()

    if project_details is None:
        # If project_details is None, it means the project_id doesn't exist for this user, or at all.
        # Check if the project exists at all to differentiate between "not yours" and "not found".
        cursor.execute("SELECT 1 FROM projects WHERE project_id = ?", (project_id,))
        if cursor.fetchone():
            return error_page("You are not authorized to view this project.", 403) # Project exists, but not for this user
        else:
            return error_page("Project not found.", 404) # Project does not exist

    project_name = project_details["name"] # Get name directly from project_details

    # Fetch all work items for this project
    cursor.execute("""SELECT *
                     FROM work_items
                     WHERE project_id = ?""", (project_id,))

    tasks = cursor.fetchall()
    tree = build_task_tree(tasks) # Build the hierarchical tree

    return render_template('tasks v4.html', tasks=tree, project_id=project_id, project_name=project_name, username=get_username(user_id))


@app.route("/projects", methods=["GET","POST"])
@login_required
def projects_list():
    """Show all user projects."""

    if request.method == "GET":
        conn = get_db()
        conn.execute("PRAGMA foreign_keys = ON")
        cursor = conn.cursor()
        user_id = session["user_id"]

        cursor.execute("""SELECT *
                          FROM projects
                          WHERE user_id = ?
                          ORDER BY name ASC""", (user_id,)) # Order projects by name

        rows = cursor.fetchall()
        rows_list = []

        for row in rows:
            rows_list.append(dict(row)) # Convert each Row object to a dict

        return render_template("projects.html", projects=rows_list, username=get_username(user_id)) # Renamed 'rows' to 'projects' for clarity

    else:
        return error_page("Request Error, Only GET requests accepted.", 403 ) 



@app.route("/save-tasks", methods=["POST"])
@login_required
def save_tasks():
    user_id = session["user_id"]
    conn = get_db()
    conn.execute("PRAGMA foreign_keys = ON")
    cursor = conn.cursor()

    try:
        data = request.get_json()
        project_id = data.get("project_id")
        tasks_data = data.get("tasks", [])
        deleted_task_ids = data.get("deleted_task_ids", [])

        print(f"Debug: Received project_id: {project_id}")
        print(f"Debug: Received tasks_data: {tasks_data}")
        print(f"Debug: Received deleted_task_ids: {deleted_task_ids}")

        # Validate project ownership
        cursor.execute("SELECT 1 FROM projects WHERE user_id = ? AND project_id = ?", (user_id, project_id))
        if not cursor.fetchone():
            return jsonify({"error": "Project not found or not owned by user."}), 403

        # 1. Handle Deletions
        if len(deleted_task_ids) > 0:
            # Convert all deletable IDs to integers in one go, filtering out "new-" or invalid IDs
            clean_deleted_ids = []
            for task_id in deleted_task_ids:
                if isinstance(task_id, str) and task_id.isdigit():
                    clean_deleted_ids.append(int(task_id))
            
            if clean_deleted_ids: # Only proceed if there are valid IDs to delete
                # Use IN clause for efficiency to delete multiple tasks
                placeholders = ','.join(['?'] * len(clean_deleted_ids))
                cursor.execute(f"""
                    DELETE FROM work_items
                    WHERE item_id IN ({placeholders}) AND project_id = ?
                """, clean_deleted_ids + [project_id])
                print(f"Debug: Deleted {cursor.rowcount} tasks with IDs: {clean_deleted_ids}")
            else:
                print(f"INFO: No valid numeric IDs found for deletion in {deleted_task_ids}")
        conn.commit() # Commit deletions before processing inserts/updates

        # 2. Process tasks for inserts/updates
        # A dictionary to map client-side temporary IDs to actual database IDs
        id_map = {}

        # Recursive function to process tasks and subtasks
        def process_task_list(task_list, parent_db_id=None):
            for task in task_list:
                client_id = task["id"]
                name = task["name"]
                description = task.get("description")
                due_date = task.get("due_date")
                completed = task.get("completed", False) # Default to False if not present
                priority = task.get("priority") # Added priority
                status = task.get("status") # Added status
                assigned_to_user_id = task.get("assigned_to_user_id") # Added assigned_to_user_id
                display_order = task.get("display_order") # Added display_order

                print(f"Debug: Processing task - client_id: '{client_id}', name: '{name}', parent_db_id: {parent_db_id}")

                current_db_id = None # Initialize current_db_id

                if isinstance(client_id, str) and client_id.startswith("new-"): # Check for new tasks
                    # This is a new task, insert it
                    cursor.execute("""
                        INSERT INTO work_items
                        (project_id, parent_item_id, name, description, due_date, is_completed, priority, status, assigned_to_user_id, display_order)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (project_id, parent_db_id, name, description, due_date, completed, priority, status, assigned_to_user_id, display_order))
                    new_db_id = cursor.lastrowid
                    id_map[client_id] = new_db_id # Map temp ID to real ID for subtasks
                    current_db_id = new_db_id
                    print(f"Debug: Inserted new task. Client ID: {client_id}, New DB ID: {new_db_id}")
                elif isinstance(client_id, (int, str)) and str(client_id).isdigit(): # Check for existing tasks (numeric ID)
                    # This is an existing task, update it
                    try:
                        current_db_id = int(client_id)
                        cursor.execute("""
                            UPDATE work_items
                            SET name = ?, description = ?, due_date = ?, is_completed = ?, 
                                priority = ?, status = ?, assigned_to_user_id = ?, display_order = ?, parent_item_id = ?
                            WHERE item_id = ? AND project_id = ?
                        """, (name, description, due_date, completed, priority, status, assigned_to_user_id, display_order, parent_db_id, current_db_id, project_id))
                        print(f"Debug: Updated existing task. DB ID: {current_db_id}, Parent ID: {parent_db_id}")
                    except ValueError:
                        print(f"ERROR: Could not convert client_id '{client_id}' to int. Skipping update for this task.")
                        continue # Continue to the next task without processing subtasks for this invalid one
                else:
                    print(f"WARNING: Skipping task '{name}' with invalid client_id '{client_id}' (expected existing numeric ID or 'new-' prefix).")
                    continue # Continue to the next task if ID is invalid

                # Recursively process subtasks ONLY if current_db_id was successfully obtained
                if current_db_id is not None and task.get("subtasks"):
                    process_task_list(task["subtasks"], current_db_id)

        # Start processing the top-level tasks
        process_task_list(tasks_data)


        conn = get_db()
        conn.execute("PRAGMA foreign_keys = ON")
        cursor = conn.cursor()

        # SQL query to update top-level work_items names to match their project name
        update_query = """
        UPDATE work_items
        SET name = (
            SELECT projects.name
            FROM projects
            WHERE work_items.project_id = projects.project_id
        )
        WHERE parent_item_id IS NULL
        AND name != (
            SELECT projects.name
            FROM projects
            WHERE work_items.project_id = projects.project_id
        )
        """
        # Execute the update
        cursor.execute(update_query)

        conn.commit() # Commit all inserts/updates

        return jsonify({"message": "Tasks saved successfully!", "new_ids_map": id_map}), 200

    except Exception as e:
        conn.rollback() # Rollback in case of error
        print(f"Error saving tasks: {e}")
        return jsonify({"error": "Internal server error", "details": str(e)}), 500


if __name__ == '__main__':
    app.run(debug=True)

