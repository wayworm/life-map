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

Initialize the Database using provided resetDatabase.py:

The project contains the database file, here is the schema used within:

-- users table
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    email TEXT UNIQUE,
    password_hash TEXT NOT NULL
);
<br><br><br><br>
-- projects table<br>
CREATE TABLE IF NOT EXISTS projects (<br>
    project_id INTEGER PRIMARY KEY AUTOINCREMENT,<br>
    user_id INTEGER NOT NULL,<br>
    name TEXT NOT NULL,<br>
    description TEXT,<br>
    start_date TEXT,<br>
    end_date TEXT,<br>
    FOREIGN KEY (user_id) REFERENCES users (user_id)<br>
);<br>
<br>
<br>
<br>
-- work_items table (tasks and subtasks)<br>
CREATE TABLE IF NOT EXISTS work_items (<br>
    item_id INTEGER PRIMARY KEY AUTOINCREMENT,<br>
    project_id INTEGER NOT NULL,<br>
    parent_item_id INTEGER, -- NULL for top-level tasks<br>
    name TEXT NOT NULL,<br>
    description TEXT,<br>
    due_date TEXT,<br>
    is_completed INTEGER DEFAULT 0, -- 0 for false, 1 for true<br>
    priority INTEGER,<br>
    status TEXT,<br>
    assigned_to_user_id INTEGER,<br>
    display_order INTEGER, -- For manual sorting<br>
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,<br>
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,<br>
    FOREIGN KEY (project_id) REFERENCES projects (project_id) ON DELETE CASCADE,<br>
    FOREIGN KEY (parent_item_id) REFERENCES work_items (item_id) ON DELETE CASCADE,<br>
    FOREIGN KEY (assigned_to_user_id) REFERENCES users (user_id)<br>
);<br>


Run the application:

python app.py

Access the application:
Open your web browser and navigate to http://127.0.0.1:5000/.

Project Structure

.
├── app.py                      
├── LifeMap.db                  >
├── static/                     
│   └── ...<br>
└── templates/                  
├── account.html              
├── error_page.html      
├── editProject.html            
├── layout.html                 
├── login.html        
├── newProject.html           
├── projects.html             
├── register.html            
└── tasks v4.html              

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

Database Schema Management: No formal database migration system (e.g., Flask-Migrate) is in place. Schema changes require manual CREATE TABLE or ALTER TABLE statements.