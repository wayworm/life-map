import sqlite3
from flask import g, session, redirect
from datetime import date
from dateutil.relativedelta import relativedelta
from functools import wraps
from google_calendar import *


def get_db():
    if "lifemap_db" not in g:
        g.lifemap_db = sqlite3.connect("LifeMap.db")
        g.lifemap_db.row_factory = sqlite3.Row
    return g.lifemap_db


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get("user_id") is None:
            return redirect("/login")
        return f(*args, **kwargs)

    return decorated_function


def build_task_tree(tasks_flat_list):
    """
    tasks_falt_list is a sqlite3 row object.
    """
    task_map = {}
    for task_row in tasks_flat_list:
        task_dict = dict(task_row)

        # Match keys to schema for consistency
        task_dict["item_id"] = task_dict["item_id"]
        task_dict["parent_item_id"] = task_dict["parent_item_id"]
        task_dict["is_completed"] = bool(task_dict["is_completed"])

        # Handle the is_minimized state
        task_dict["is_minimized"] = bool(task_dict["is_minimized"])
        task_dict["subtasks"] = []
        task_dict["planned_hours"] = task_dict["planned_hours"]
        task_map[task_dict["item_id"]] = task_dict

    tree = []
    for item_id, task in task_map.items():
        if task["parent_item_id"] and task["parent_item_id"] in task_map:
            task_map[task["parent_item_id"]]["subtasks"].append(task)
        elif not task["parent_item_id"]:
            tree.append(task)

    def calculate_rolled_up_hours(task):
        if not task["subtasks"]:
            task["calculated_planned_hours"] = task.get("planned_hours") or 0.0
            return task["calculated_planned_hours"]

        total_hours = 0.0
        for subtask in task["subtasks"]:
            total_hours += calculate_rolled_up_hours(subtask)

        task["calculated_planned_hours"] = total_hours
        return total_hours

    def sort_and_calculate_recursive(tasks_list):
        tasks_list.sort(key=lambda t: t.get("display_order", t["item_id"]))
        for t in tasks_list:
            if t["subtasks"]:
                sort_and_calculate_recursive(t["subtasks"])
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
    if not target_date_str:
        return "No due date"
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


def process_task_list(
    task_list, cursor, id_map, project_id, existing_google_events, parent_db_id=None
):
    """
    Recursively processes a list of tasks to save them to the database.
    """
    for task in task_list:
        client_id = task.get("item_id")
        name = task.get("name")
        description = task.get("description")
        due_date = task.get("due_date") or None
        is_completed = 1 if task.get("is_completed", False) else 0
        is_minimized = 1 if task.get("is_minimized", False) else 0
        display_order = task.get("display_order", 0)
        planned_hours = task.get("planned_hours")
        actual_parent_id = task.get("parent_item_id")

        if isinstance(actual_parent_id, str) and actual_parent_id.startswith("new-"):
            actual_parent_id = id_map.get(actual_parent_id)

        current_db_id = None

        if isinstance(client_id, str) and client_id.startswith("new-"):
            # New tasks are inserted using the corrected parent ID.
            cursor.execute(
                """
                INSERT INTO work_items (project_id, parent_item_id, name, description, due_date, is_completed, is_minimized, display_order, planned_hours)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    project_id,
                    actual_parent_id,
                    name,
                    description,
                    due_date,
                    is_completed,
                    is_minimized,
                    display_order,
                    planned_hours,
                ),
            )

            current_db_id = cursor.lastrowid
            id_map[client_id] = current_db_id

        elif str(client_id).isdigit():
            # Existing tasks are updated using the corrected parent ID.
            current_db_id = int(client_id)
            cursor.execute(
                """
                UPDATE work_items
                SET name = ?, description = ?, due_date = ?, is_completed = ?, is_minimized = ?, display_order = ?, planned_hours = ?, parent_item_id = ?
                WHERE item_id = ? AND project_id = ?
            """,
                (
                    name,
                    description,
                    due_date,
                    is_completed,
                    is_minimized,
                    display_order,
                    planned_hours,
                    actual_parent_id,
                    current_db_id,
                    project_id,
                ),
            )

        # If the task has subtasks, process them recursively.
        if current_db_id and task.get("subtasks"):
            # Pass the existing_google_events dictionary down to the recursion
            process_task_list(
                task["subtasks"],
                cursor,
                id_map,
                project_id,
                existing_google_events,
                current_db_id,
            )


        if str(client_id).isdigit():
            old_event_id = existing_google_events.get(current_db_id)
            if old_event_id:
                delete_google_event(old_event_id)

        # If the task has a due date, create a new event.
        if due_date:
            event_data = {
                "summary": name,
                "description": description or "No description provided.",
                "start": {"date": due_date},
                "end": {"date": due_date},
            }
            created_event = pushOutgoingEvents(event_data)

            if created_event and current_db_id:
                event_id = created_event.get("id")
                cursor.execute(
                    "UPDATE work_items SET google_calendar_event_id = ? WHERE item_id = ?",
                    (event_id, current_db_id),
                )
        elif str(client_id).isdigit():
            cursor.execute(
                "UPDATE work_items SET google_calendar_event_id = NULL WHERE item_id = ?",
                (current_db_id,),
            )


def gap_print(a, b):
    print("\n" * b)
    print(a)
    print("\n" * b)
