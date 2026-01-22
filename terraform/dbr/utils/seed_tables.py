import json
import os
import sys
from databricks import sql

# This script seeds the 'test_data' table in each student group's schema.
# Usage: 
#   1. pip install databricks-sql-connector
#   2. terraform output -json sp_credentials_and_env_vars > all_groups.json
#   3. python3 utils/seed_tables.py

def seed_tables():
    json_input = "all_groups.json"
    
    if not os.path.exists(json_input):
        print(f"Error: {json_input} not found.")
        print("Run: terraform output -json sp_credentials_and_env_vars > all_groups.json")
        sys.exit(1)

    with open(json_input, "r") as f:
        groups_data = json.load(f)

    # We need a valid connection configuration.
    # We can pick the first group's config to find the HOST and SQL_ID.
    # Authentication will use your local Databricks CLI profile (or env vars).
    # Ensure you are logged in via 'databricks auth login' or have env vars set.
    
    first_group = list(groups_data.values())[0]
    server_hostname = first_group["DATABRICKS_HOST"].replace("https://", "").replace("/", "")
    http_path = f"/sql/1.0/warehouses/{first_group['DATABRICKS_SQL_ID']}"
    
    # Check for Access Token (from env or manual input)
    access_token = os.getenv("DATABRICKS_TOKEN")
    if not access_token:
        print("⚠️  Warning: DATABRICKS_TOKEN env var not set.")
        print("   Using Azure CLI token (az account get-access-token ...)")
        # Simple helper to get token if az cli is installed
        try:
            import subprocess
            result = subprocess.run(
                ["az", "account", "get-access-token", "--resource", "2ff814a6-3304-4ab8-85cb-cd0e6f879c1d", "--query", "accessToken", "-o", "tsv"],
                capture_output=True, text=True
            )
            if result.returncode == 0:
                access_token = result.stdout.strip()
            else:
                raise Exception("Could not get Azure token")
        except Exception as e:
            print(f"   Failed to get Azure token: {e}")
            sys.exit("Please set DATABRICKS_TOKEN environment variable.")

    print(f"Connecting to {server_hostname} (Warehouse: {first_group['DATABRICKS_SQL_ID']})...")

    try:
        with sql.connect(
            server_hostname=server_hostname,
            http_path=http_path,
            access_token=access_token
        ) as connection:
            
            with connection.cursor() as cursor:
                for group_id, config in groups_data.items():
                    catalog = config["DATABRICKS_CATALOG"]
                    schema = config["DATABRICKS_SCHEMA"]
                    table_full_name = f"{catalog}.{schema}.test_data"
                    
                    print(f"[{group_id}] Seeding {table_full_name}...", end=" ", flush=True)
                    
                    try:
                        # 1. Create Table
                        cursor.execute(f"""
                            CREATE TABLE IF NOT EXISTS {table_full_name} (
                                id INT,
                                description STRING
                            ) USING DELTA
                        """)
                        
                        # 2. Insert Data (Idempotent)
                        cursor.execute(f"""
                            INSERT INTO {table_full_name}
                            SELECT 1, 'Hello World from Admin Script'
                            WHERE NOT EXISTS (
                                SELECT 1 FROM {table_full_name} WHERE id = 1
                            )
                        """)
                        print("✅")
                        
                    except Exception as e:
                        print(f"❌ Error: {e}")

    except Exception as e:
        print(f"Connection Failed: {e}")

if __name__ == "__main__":
    seed_tables()
