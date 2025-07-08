# LifeMap
LifeMap is an intuitive web application designed to help you conquer your goals by breaking down large projects into manageable, hierarchical tasks. Organize everything from a simple to-do list to a complex, multi-layered project with an easy-to-use drag-and-drop interface.

![LifeMap Projects Page](https://imgur.com/a/QiaV9wq) <!-- It's recommended to replace this with a real screenshot or GIF of your application in action! -->

---

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

---

## Tech Stack

* **Backend:** Python (Flask), Flask-Session, Werkzeug
* **Frontend:** HTML5, CSS3, JavaScript (ES6+), Jinja
* **Styling & UI:** Bootstrap 5, Font Awesome
* **Database:** SQLite
* **JS Libraries:** SortableJS (for drag-and-drop), FullCalendar (for calendar view)

---

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
    The project comes with a `LifeMap.db` file. The schema is detailed below. You can run the included `resetDatabase.py` to reset it if needed.

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


