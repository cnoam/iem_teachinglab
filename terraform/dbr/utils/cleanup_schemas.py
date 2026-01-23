# gemini 2026-01-23 05:07
import os
import argparse
import requests # Still needed for other potential uses, though not directly for SP OAuth now
from databricks import sql

# Removed get_oauth_token function as SP authentication is no longer supported

def get_connection(host, sql_warehouse_id, auth_token):
    """Establishes a connection to the Databricks SQL Warehouse using a token."""
    http_path = f"/sql/1.0/warehouses/{sql_warehouse_id}"
    return sql.connect(
        server_hostname=host,
        http_path=http_path,
        access_token=auth_token
    )

def list_schemas(cursor, catalog):
    """Returns a list of schema names in the given catalog, excluding system schemas."""
    cursor.execute(f"SHOW SCHEMAS IN `{catalog}`")
    system_schemas = ["information_schema", "default"] # Schemas to exclude from cleanup
    return [row.databaseName for row in cursor.fetchall() if row.databaseName not in system_schemas]

def list_objects_in_schema(cursor, catalog, schema):
    """Returns a list of table/view names in the given schema."""
    cursor.execute(f"SHOW TABLES IN `{catalog}`.`{schema}`")
    # The 'tableName' column contains the name of the table/view
    return [f"`{catalog}`.`{schema}`.`{row.tableName}`" for row in cursor.fetchall()]

def main():
    parser = argparse.ArgumentParser(description="Clean all tables and views from schemas in a Databricks catalog.")
    parser.add_argument("--catalog", required=True, help="The name of the catalog to clean.")
    parser.add_argument("--host", help="Databricks host URL (e.g., adb-....azuredatabricks.net). Defaults to DATABRICKS_HOST env var.")
    parser.add_argument("--sql-id", help="Databricks SQL Warehouse ID. Defaults to DATABRICKS_SQL_ID env var.")
    # Removed --client-id and --client-secret arguments
    parser.add_argument("--token", help="Databricks Personal Access Token. Defaults to DATABRICKS_TOKEN env var.")
    parser.add_argument("--yes", action="store_true", help="Skip confirmation prompt and proceed with deletion.")
    
    args = parser.parse_args()

    # Get connection details from args or environment variables
    host = args.host or os.getenv("DATABRICKS_HOST")
    sql_id = args.sql_id or os.getenv("DATABRICKS_SQL_ID")
    token = args.token or os.getenv("DATABRICKS_TOKEN")


    # Removed client_id and client_secret env var checks

    if not all([host, sql_id]):
        print("Error: --host and --sql-id arguments (or their corresponding environment variables) are required.")
        return

    print("--- Databricks Schema Cleanup ---")
    
    auth_token = token
    if not auth_token:
        print("Error: A Personal Access Token is required. Provide it via --token or DATABRICKS_TOKEN environment variable.")
        return

    objects_to_delete = []
    try:
        # Use the obtained token for connection
        with get_connection(host.replace("https://", ""), sql_id, auth_token) as connection:
            with connection.cursor() as cursor:
                print(f"Fetching schemas from catalog '{args.catalog}' using SQL Warehouse '{sql_id}'...")
                schemas = list_schemas(cursor, args.catalog)
                print(f"Found {len(schemas)} schemas.")

                for schema in schemas:
                    print(f"  Fetching objects from schema '{schema}'...")
                    objects_in_schema = list_objects_in_schema(cursor, args.catalog, schema)
                    if objects_in_schema:
                        objects_to_delete.extend(objects_in_schema)
    except Exception as e:
        if "SQL endpoint" in str(e) and "not found" in str(e):
            print(f"\nWarning: SQL Warehouse '{sql_id}' not found. Assuming no objects to clean up.")
            return # Exit gracefully if warehouse is gone
        else:
            print(f"\nError connecting to Databricks or fetching objects: {e}")
            return

    if not objects_to_delete:
        print("\nNo tables or views found in any schema. Nothing to do.")
        return

    print("\nThe following tables/views will be permanently deleted:")
    for obj_name in objects_to_delete:
        print(f"  - {obj_name}")

    if not args.yes:
        confirm = input("\nAre you sure you want to proceed? Type 'yes' to confirm: ")
        if confirm.lower() != 'yes':
            print("Aborted by user.")
            return

    print("\nStarting deletion...")
    try:
        with get_connection(host.replace("https://", ""), sql_id, auth_token) as connection:
            with connection.cursor() as cursor:
                for obj_name in objects_to_delete:
                    try:
                        cursor.execute(f"DROP TABLE IF EXISTS {obj_name}")
                        print(f"  DELETED: {obj_name}")
                    except Exception as e:
                        print(f"  ERROR deleting {obj_name}: {e}")
                print("Cleanup complete.")
    except Exception as e:
        print(f"\nAn error occurred during deletion: {e}")

if __name__ == "__main__":
    main()
