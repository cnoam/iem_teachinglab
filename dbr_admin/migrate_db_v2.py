import sqlite3
import datetime
import sys
import os

DEFAULT_DB_PATH = '../cluster_uptimes.db'

def get_db_connection(db_path):
    return sqlite3.connect(db_path)

def table_exists(cursor, table_name):
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table_name,))
    return cursor.fetchone() is not None

def column_exists(cursor, table_name, column_name):
    cursor.execute(f"PRAGMA table_info({table_name})")
    columns = [row[1] for row in cursor.fetchall()]
    return column_name in columns

def migrate_v1(cursor):
    """
    Version 1 Migration:
    - Rename 'clusteruptime' -> 'cluster_uptimes'
    - Rename 'id' -> 'cluster_id'
    - Add 'last_poll_time'
    - Add 'start_time' (migrating from 'start_timestamp')
    - Drop 'start_timestamp'
    """
    print("Applying migration to version 1...")

    # 1. Rename table 'clusteruptime' -> 'cluster_uptimes'
    if table_exists(cursor, 'clusteruptime'):
        if not table_exists(cursor, 'cluster_uptimes'):
            print("Renaming table 'clusteruptime' to 'cluster_uptimes'...")
            cursor.execute("ALTER TABLE clusteruptime RENAME TO cluster_uptimes")
        else:
            print("Both 'clusteruptime' and 'cluster_uptimes' exist. Assuming 'cluster_uptimes' is correct.")

    if not table_exists(cursor, 'cluster_uptimes'):
        print("Target table 'cluster_uptimes' missing. Skipping v1 migration steps for this table.")
        # If the table is missing, maybe it's a fresh DB?
        return

    # 2. Rename column 'id' -> 'cluster_id'
    if column_exists(cursor, 'cluster_uptimes', 'id'):
        if not column_exists(cursor, 'cluster_uptimes', 'cluster_id'):
            print("Renaming column 'id' to 'cluster_id'...")
            cursor.execute("ALTER TABLE cluster_uptimes RENAME COLUMN id TO cluster_id")
    
    # 3. Add 'last_poll_time'
    if not column_exists(cursor, 'cluster_uptimes', 'last_poll_time'):
        print("Adding column 'last_poll_time'...")
        cursor.execute("ALTER TABLE cluster_uptimes ADD COLUMN last_poll_time DATETIME")
    
    # 4. Add 'start_time' and migrate data
    if not column_exists(cursor, 'cluster_uptimes', 'start_time'):
        print("Adding column 'start_time'...")
        cursor.execute("ALTER TABLE cluster_uptimes ADD COLUMN start_time DATETIME")
        
        if column_exists(cursor, 'cluster_uptimes', 'start_timestamp'):
            print("Migrating data from 'start_timestamp'...")
            cursor.execute("SELECT cluster_id, start_timestamp FROM cluster_uptimes WHERE start_timestamp IS NOT NULL")
            rows = cursor.fetchall()
            for row_id, ts in rows:
                if ts:
                    try:
                        dt_str = datetime.datetime.fromtimestamp(ts).isoformat(sep=' ')
                        cursor.execute("UPDATE cluster_uptimes SET start_time = ? WHERE cluster_id = ?", (dt_str, row_id))
                    except Exception as e:
                        print(f"Error converting timestamp {ts}: {e}")
    
    # 5. Drop 'start_timestamp'
    if column_exists(cursor, 'cluster_uptimes', 'start_timestamp'):
         print("Dropping column 'start_timestamp'...")
         cursor.execute("ALTER TABLE cluster_uptimes DROP COLUMN start_timestamp")

def migrate_db():
    db_path = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_DB_PATH
    
    if not os.path.exists(db_path):
        print(f"Database file not found at {db_path}")
        return

    print(f"Checking database: {db_path}")
    conn = get_db_connection(db_path)
    cursor = conn.cursor()

    try:
        cursor.execute("PRAGMA user_version")
        current_version = cursor.fetchone()[0]
        print(f"Current DB version: {current_version}")

        if current_version < 1:
            migrate_v1(cursor)
            cursor.execute(f"PRAGMA user_version = 1")
            print("Updated DB version to 1")
        else:
            print("Database is already at version 1 or higher.")
        
        # Future: if current_version < 2: migrate_v2(cursor)...

        conn.commit()
        print("Migration process finished.")

    except Exception as e:
        print(f"An error occurred: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    migrate_db()