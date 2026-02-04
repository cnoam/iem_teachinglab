import os
import requests
import uuid
from dotenv import load_dotenv

# Load the same .env file used by the Flask app
load_dotenv()

# Colors for terminal output
GREEN = "\033[92m"
RED = "\033[91m"
RESET = "\033[0m"

def test_step(name, func):
    print(f"Testing {name}...", end=" ", flush=True)
    try:
        func()
        print(f"{GREEN}PASS{RESET}")
    except Exception as e:
        print(f"{RED}FAIL{RESET}")
        print(f"   Error: {e}")

def run_tests():
    config = {
        "host": os.getenv("DATABRICKS_HOST"),
        "id": os.getenv("DATABRICKS_CLIENT_ID"),
        "secret": os.getenv("DATABRICKS_CLIENT_SECRET"),
        "cluster_id": os.getenv("DATABRICKS_CLUSTER_ID"),
        "sql_id": os.getenv("DATABRICKS_SQL_ID"),
        "catalog": os.getenv("DATABRICKS_CATALOG"),
        "schema": os.getenv("DATABRICKS_SCHEMA")
    }

    if any( v is None for v in config.values()):
        print(f"{RED}Missing Environment Variables:{RESET}")
        for k, v in config.items():
            if v is None:
                print(f" - {k}")
        raise ValueError("Environment incomplete")
    
    token_container = {}

    # 1. Test OAuth Handshake
    def test_oauth():
        url = f"{config['host']}/oidc/v1/token"
        data = {"grant_type": "client_credentials", "scope": "all-apis"}
        resp = requests.post(url, data=data, auth=(config['id'], config['secret']), timeout=10)
        resp.raise_for_status()
        token_container['token'] = resp.json().get("access_token")
    
    test_step("OAuth Authentication", test_oauth)

    if 'token' not in token_container:
        return

    headers = {"Authorization": f"Bearer {token_container['token']}"}

    # 2. Test Cluster Access
    def test_cluster():
        url = f"{config['host']}/api/2.0/clusters/get?cluster_id={config['cluster_id']}"
        resp = requests.get(url, headers=headers, timeout=10)
        resp.raise_for_status()
    
    test_step("Cluster Access", test_cluster)

    # 3. Test SQL Warehouse & Permissions (Create/Drop)
    def test_sql_permissions():
        # First check Warehouse existence
        url = f"{config['host']}/api/2.0/sql/warehouses/{config['sql_id']}"
        resp = requests.get(url, headers=headers, timeout=10)
        resp.raise_for_status()

        # Try to CREATE and then DROP a table to prove write permissions
        sql_url = f"{config['host']}/api/2.0/sql/statements"
        
        # Unique table name to avoid collisions if multiple people run this
        test_table = f"test_conn_{uuid.uuid4().hex[:8]}"
        
        # CREATE
        create_query = {
            "warehouse_id": config['sql_id'],
            "statement": f"CREATE TABLE {config['catalog']}.{config['schema']}.{test_table} (id INT)",
            "wait_timeout": "15s"
        }
        resp = requests.post(sql_url, headers=headers, json=create_query, timeout=20)
        resp.raise_for_status()
        if resp.json().get('status', {}).get('state') == 'FAILED':
             raise Exception("CREATE TABLE Failed: " + str(resp.json().get('status', {}).get('error')))

        # DROP
        drop_query = {
            "warehouse_id": config['sql_id'],
            "statement": f"DROP TABLE {config['catalog']}.{config['schema']}.{test_table}",
            "wait_timeout": "15s"
        }
        resp = requests.post(sql_url, headers=headers, json=drop_query, timeout=20)
        resp.raise_for_status()
        if resp.json().get('status', {}).get('state') == 'FAILED':
             print(f"{RED}Warning: Failed to cleanup table {test_table}{RESET}")

    test_step("SQL Warehouse Read/Write Access", test_sql_permissions)

if __name__ == "__main__":
    print("--- Databricks Permission Validator ---")
    run_tests()
    print("---------------------------------------")
