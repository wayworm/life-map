
---

# LifeMap: The Hierarchical Task Manager

[Video Demo](https://www.youtube.com/watch?v=c_FUCnUCZVE)

![LifeMap Projects Page](https://imgur.com/a/QiaV9wq)

## Core Features

* **Project Dashboard:** View all your projects at a glance. See their descriptions and quickly assess upcoming deadlines with a human-readable "due in" timeline (e.g., "Due this week", "Due in 3 months").

* **Hierarchical Task Management:** This is the heart of LifeMap.
    * **Nesting:** Create tasks and break them down into as subtasks nested up to 6 layers deep.
    * **Drag & Drop:** Intuitively reorder tasks and change their hierarchy simply by dragging them.
    * **Smart Completion:** Marking a parent task as "complete" automatically completes all its children. Unchecking a subtask intelligently un-marks its parents, ensuring your project status is always accurate.
    * **Automatic Hour Calculation:** Parent tasks automatically sum the "planned hours" of their subtasks, giving you an instant overview of the total effort required.

* **Calendar View:** All your tasks with due dates are automatically populated into a clean, full-featured calendar, allowing you to visualize your schedule and deadlines across all projects.

* **Full User Control:**
    * **Secure Authentication:** Standard user registration and login system with password hashing to keep your account secure.
    * **Account Management:** Easily change your username or reset your password from a simple account page.


## Description

LifeMap is an intuitive and powerful web application designed to help you conquer your most ambitious goals by breaking down large projects into manageable, hierarchical tasks. Moving beyond simple to-do lists, LifeMap provides a visual and interactive workspace where you can structure your work logically, track your progress effortlessly, and visualize your deadlines. It would be appropriate for large projects such as planning a complex software build, outlining a novel, or even just organizing your week, LifeMap gives you the tools to see both the big picture and the finest details.

The core of LifeMap is its nested task system. Users can create projects and then populate them with tasks that can be broken down into subtasks, up to six levels deep. This structure allows for a natural decomposition of work. To make this system feel fluid and intuitive, the interface is built around a drag-and-drop mechanic, allowing you to reorder tasks and even change their parentage on the fly, and each leayer of subtask is assigned it's own colour, for visual clarity.

To ensure accuracy and save time, the application features intelligent automation. When you mark a parent task as complete, all of its subtasks are automatically marked as complete as well. Conversely, if you uncheck a subtask, its parent tasks are intelligently "woken up" and marked as incomplete, ensuring a project's status is always a true reflection of the work remaining. Furthermore, the system automatically calculates the total "planned hours" for parent tasks by summing the hours of their children, providing an instant, dynamic overview of the effort required at every level of your project. All tasks with due dates are also automatically pushed to an integrated calendar view and synced with your primary Google Calendar, giving you a unified view of your schedule.

## Pages

### Register page

This screen allows new users to create an account. It includes fields for username, an optional email, password, and password confirmation. To enhance usability, "Show Password" checkboxes are provided to toggle the visibility of the password fields.

### Log In page

The login page is for existing users to access their accounts. It features input fields for either a username or email and a password. A "Show Current Password" option is available to make the password visible.

### New Project page

Users can create a new project on this screen. It provides a form with fields for the project's title, a detailed description, a start date, and a due date.

### Edit Project Details page

This page enables users to modify the information of an existing project. It contains forms to edit the project title and description. Functionality to save the changes, cancel the edit, or delete the entire project is also included.

### My Projects page

This screen displays a comprehensive list of all the user's projects in a table format, showing the project name, description, and due date. Due dates falling within the current week are highlighted for urgency. Each project listed has options to view its associated tasks or to edit the project details. A button to "Add New Project" is also present.

### Tasks page

The tasks screen provides a detailed, hierarchical view for managing a project's tasks and subtasks. Users can add, edit, and delete tasks, mark them as complete, and assign planned hours and due dates. The interface supports drag-and-drop for reordering tasks and allows for the collapsing and expanding of subtask lists. The total remaining time for the project is also displayed.

### Google Calendar page

This page features an integration with Google Calendar to display projects and tasks in a calendar format. Users can view events in month, week, or day layouts. Hovering over an event reveals more details, such as the title and start time.

### Account page

On the account screen, users can manage their personal settings. It is divided into two main sections: one for changing the account username and another for resetting the password, which requires the current password and a new password confirmation.

### Error page

This page shows if the the application runs into an error, or otherwise if the user provides invalid input. Alerts are used instead of this page in many places, though it is still seen during invalid inputs during Log In and Registration.



## File Breakdown

This project is composed of several key files that work together to deliver the full LifeMap experience.

### app.py (Main Application):
 This is the heart of the backend. Built with Flask, it manages the server-side logic. It handles URL routing, user authentication (registration, login, logout), and session management. It contains all the endpoints for creating, reading, updating, and deleting projects and tasks. This file interfaces directly with the SQLite database to persist all user data and orchestrates calls to helper modules for more specific functionality, such as processing task data or interacting with the Google Calendar API.

### tasks.js (Frontend Logic):
This file brings the task management page to life. It is responsible for all the dynamic, client-side functionality. This includes creating new subtasks, deleting existing ones, and handling the logic for the drag-and-drop interface using the SortableJS library. It also performs real-time calculations, such as updating the "Remaining Hours" display and rolling up planned hours from subtasks to their parents. Finally, it collects all the task data from the webpage, packages it into a JSON payload, and sends it to the Flask backend via an AJAX fetch request when the user saves their changes.

### google_calendar.py (Google Calendar Integration):
This module isolates all interactions with the Google Calendar API. It manages OAuth 2.0 authentication, storing tokens securely to maintain a connection to the user's Google account. Its primary functions are to pushOutgoingEvents, which creates or updates an event on the user's primary calendar, and delete_google_event, which removes one. This modular approach keeps API-specific code separate from the main application logic, making it easier to manage and debug.

### help.py (Helper Utilities):

This file contains essential functions that are used across the application. It manages the database connection (get_db) and includes the @login_required decorator to protect routes that should only be accessible to logged-in users. Its most critical function is process_task_list, a recursive function that processes the nested task data sent from the frontend. It intelligently handles updates to existing tasks and the creation of new ones, resolving temporary client-side IDs into permanent database IDs. It also contains the logic to build the hierarchical task tree from a flat list retrieved from the database.


## Design Choices

Several key decisions were made during the development of LifeMap to balance functionality, performance, and user experience.

### Hierarchical Data Management:
The decision to manage task hierarchy on both the client and server was intentional. The frontend (tasks.js) allows for a fluid user experience with instant visual feedback via drag-and-drop. However, the definitive state is always managed on the backend. When the user saves, the entire task tree structure is sent to the server. The process_task_list function in help.py then recursively traverses this structure. This server-side validation and processing ensures data integrity, preventing issues like orphaned tasks or circular dependencies.

### Google Calendar Sync Strategy:
When a task's due date is updated, the application does not attempt to find and modify the existing Google Calendar event. Instead, it simply deletes the old event and creates a new one. This "delete-then-create" approach is significantly simpler and more robust. It avoids the complexity of tracking changes and determining what specific fields of a calendar event need to be patched. While it might seem less efficient, it guarantees that the calendar event is always a perfect mirror of the task's current state (name, description, and due date).

### Client-Side Hour Calculation:
The decision to have the parent task hours and the "Remaining Hours" calculated on the client-side (tasks.js) was made to provide a responsive user experience. If these calculations were server-side, the user would need to save and reload the page to see the impact of their changes. By performing these calculations in the browser, users get immediate feedback as they adjust planned hours or mark tasks as complete, making the application feel more dynamic and interactive.

### Database Choice (SQLite):
SQLite was chosen for its simplicity, ease of setup and that it was familiar to me. Since LifeMap is designed as a single-user or small-scale application, the overhead of a larger database system like PostgreSQL or MySQL was unnecessary. SQLite is file-based, requires no separate server process, and is perfectly capable of handling the relational data (users, projects, tasks) for this project's scope, making it ideal for development and deployment.

## Tech Stack

* **Backend:** Python (Flask), Flask-Session, Werkzeug
* **Frontend:** HTML5, CSS3, JavaScript (ES6+), Jinja
* **Styling & UI:** Bootstrap 5, Font Awesome, Tailwind
* **Database:** SQLite
* **JS Libraries:** SortableJS (for drag-and-drop), FullCalendar (for calendar view)

## Setup and Installation

1.  **Clone the Repository**
    ```bash
    git clone [https://github.com/your-username/LifeMap.git](https://github.com/wayworm/LifeMap.git)
    cd LifeMap
    ```

2.  **Install Dependencies**
    ```bash
    pip install -r requirements.txt
    ```

3.  **Initialize the Database**
    The project comes with a `LifeMap.db` file. The schema is detailed below. You can run the included `resetDatabase.py` directly to reset it if needed.

    <details>
    <summary>Click to view Database Schema</summary>

    **Users Table**
    ```sql
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT NOT NULL UNIQUE,
        email TEXT UNIQUE,
        password_hash TEXT NOT NULL
    );
    ```

    **Projects Table**
    ```sql
    CREATE TABLE IF NOT EXISTS projects (
        project_id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        name TEXT NOT NULL,
        description TEXT,
        start_date TEXT,
        end_date TEXT,
        FOREIGN KEY (user_id) REFERENCES users (user_id)
    );
    ```

    **Work Items Table (Tasks & Subtasks)**
    ```sql
    CREATE TABLE IF NOT EXISTS work_items (
        item_id INTEGER PRIMARY KEY AUTOINCREMENT,
        project_id INTEGER NOT NULL,
        parent_item_id INTEGER,
        name TEXT NOT NULL,
        description TEXT,
        due_date TEXT,
        is_completed INTEGER DEFAULT 0,
        planned_hours REAL,
        display_order INTEGER,
        is_minimized INTEGER DEFAULT 0,
        google_calendar_event_id TEXT,
        FOREIGN KEY (project_id) REFERENCES projects (project_id) ON DELETE CASCADE,
        FOREIGN KEY (parent_item_id) REFERENCES work_items (item_id) ON DELETE CASCADE
    );
    ```
    </details>

4.  **Run the Application**
    ```bash
    python app.py
    ```

5.  **Access LifeMap**
    Open your browser and navigate to `http://127.0.0.1:5000/`.


