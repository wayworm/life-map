### LifeMap

LifeMap is a Flask-based web application for managing personal projects and hierarchical tasks. Users can register, log in, create new projects, and organize tasks and subtasks within those projects.

#### Features
- ##### User Authentication:

        User registration with password hashing.

        User login and session management.

        Password change functionality.

- ##### Project Management:

        Create new projects with title, description, start date, and due date.

        View a list of all owned projects.

        Edit project titles. 

- ##### Task Management:

        Hierarchical task structure (tasks and subtasks).

        Add, edit, and delete tasks and subtasks.

        Mark tasks as complete/incomplete.

        Tasks inherit completion status downwards; uncompleting a child uncompletes parents.

        Input fields for task name, description, due date, and planned hours.

        Dynamic addition and deletion of tasks/subtasks without page refresh.

        Client-side temporary IDs for new tasks, mapped to database IDs on save.

        Visual indication of task hierarchy using indentation and color coding.

        Collapse/expand subtask lists.

- ##### Database:

        SQLite database (LifeMap.db) for storing user, project, and task data.

- ##### Responsive Design:

        Utilizes Bootstrap 5 and Font Awesome for styling and icons.

        Includes custom CSS for enhanced aesthetics.

## Technologies Used

Backend: Flask (Python)

Database: SQLite3

- ##### Frontend:

        HTML5

        CSS3 (Custom styles, Bootstrap 5)

        JavaScript (ES6+)

        Jinja2 (Templating engine)

- ##### Libraries/Frameworks:

        Flask-Session

        Werkzeug for password hashing

        Bootstrap 5 (via CDN)

        Font Awesome (via CDN)

## Setup and Installation
Prerequisites

Python 3.x

pip (Python package installer)

Steps

Clone the repository:

git clone <repository_url>
cd LifeMap

Install Python dependencies located in the requirements.txt

Initialize the Database:
The application will automatically create LifeMap.db and necessary tables on its first run if they don't exist. You may need to manually create the schema for users, projects, and work_items tables.

Example Schema (to be created manually or via an initial migration script):

-- users table
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    email TEXT UNIQUE,
    password_hash TEXT NOT NULL
);

-- projects table
CREATE TABLE IF NOT EXISTS projects (
    project_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    description TEXT,
    start_date TEXT,
    end_date TEXT,
    FOREIGN KEY (user_id) REFERENCES users (user_id)
);

-- work_items table (tasks and subtasks)
CREATE TABLE IF NOT EXISTS work_items (
    item_id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL,
    parent_item_id INTEGER, -- NULL for top-level tasks
    name TEXT NOT NULL,
    description TEXT,
    due_date TEXT,
    is_completed INTEGER DEFAULT 0, -- 0 for false, 1 for true
    priority INTEGER,
    status TEXT,
    assigned_to_user_id INTEGER,
    display_order INTEGER, -- For manual sorting
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (project_id) REFERENCES projects (project_id) ON DELETE CASCADE,
    FOREIGN KEY (parent_item_id) REFERENCES work_items (item_id) ON DELETE CASCADE,
    FOREIGN KEY (assigned_to_user_id) REFERENCES users (user_id)
);

Note: The ON DELETE CASCADE clauses in work_items table are crucial for automatically deleting subtasks when a parent task or project is deleted. Ensure your CREATE TABLE statements include these if you want this behavior.

Run the application:

python app.py

Access the application:
Open your web browser and navigate to http://127.0.0.1:5000/.

Project Structure

.
├── app.py                  # Main Flask application file
├── helpers.py              # (Missing) Placeholder for login_required decorator
├── LifeMap.db              # SQLite database file (generated on run)
├── static/                 # Static assets (CSS, JS, images - if any)
│   └── ...
└── templates/              # HTML templates (Jinja2)
├── account.html        # Account management page
├── apology.html        # Error display page
├── editProject.html    # Edit project details page
├── layout.html         # Base template for all pages (header, footer, common styles)
├── login.html          # User login page
├── newProject.html     # Create new project page
├── projects.html       # List of user's projects
├── register.html       # User registration page
└── tasks v4.html       # Project-specific task management page

Usage

Register: Create a new user account.

Log In: Access your dashboard.

New Project: Create a project from the "New Project" link.

My Projects: View your projects. Click "Tasks" to manage tasks within a project.

Task Management:

    The project name acts as the top-level task.

    Add subtasks using "Add Subtask" buttons.

    Edit task names, descriptions, and due dates directly.

    Mark tasks as "Completed" using checkboxes.

    Delete tasks using the "Delete" button (subtasks will also be removed from display).

    "Save All Tasks" button persists changes to the database.

Potential Improvements and Known Issues

Missing helpers.py: The login_required decorator's implementation is not provided. Its correct functionality is assumed.

Database Schema Management: No formal database migration system (e.g., Flask-Migrate) is in place. Schema changes require manual CREATE TABLE or ALTER TABLE statements.

Error Handling Detail: Error messages returned to the user (e.g., from register or newProject) can be verbose. Production environments require more generic error messages to prevent information leakage.

Client-Side ID Refresh: After saving tasks, the entire page reloads to synchronize client-side temporary IDs with database IDs. A more efficient approach would be to update DOM elements dynamically using the new_ids_map returned by the backend.

Parent-Child Completion Logic: While propagation downwards and upwards is implemented, complex scenarios (e.g., unchecking a parent when only some children are unchecked) may require further refinement for complete consistency.

No "Planned Hours" Save Logic: The planned_hours input field is present in tasks v4.html but its value is not collected or saved in the save_tasks endpoint in app.py.

Project Name Update in work_items: The edit_project route's update for the top-level work_item name relies on the AND name = (SELECT name FROM projects WHERE project_id = ?) clause. This means the top-level task name will only update if it still matches the old project name. It should update unconditionally for the parent_item_id IS NULL work item linked to that project_id.

Database Connection Closing: The conn.close() in save_tasks's finally block is redundant if app.teardown_appcontext is properly configured to close the database connection at the end of each request. This can cause issues.