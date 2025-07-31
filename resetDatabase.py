import sqlite3


def delete_all_records(db_path="LifeMap.db"):
    """
    Deletes all records from all tables in the specified SQLite database.
    Retains table schema.
    """
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()

        if not tables:
            print(f"No tables found in {db_path}.")
            return

        print(f"Deleting all records from tables in {db_path}:")

        for table_name_tuple in tables:
            table_name = table_name_tuple[0]
            if (
                table_name == "sqlite_sequence"
            ):  # Skip sqlite_sequence table which manages AUTOINCREMENT
                continue

            print(f"  - Deleting from '{table_name}'...")
            cursor.execute(f"DELETE FROM {table_name};")
            print(f"    Deleted {cursor.rowcount} rows.")

        conn.commit()
        print("All records deleted successfully from all tables.")

    except sqlite3.Error as e:
        print(f"Database error: {e}")
        if conn:
            conn.rollback()  # Rollback changes on error
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
    finally:
        if conn:
            conn.close()


# Specify the path to database file
database_file = "LifeMap.db"
delete_all_records(database_file)
