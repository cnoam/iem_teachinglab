import os
import time
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

    HTTP_TIMEOUT = 15  # seconds - socket-level HTTP timeout (unrelated to Databricks wait_timeout in the payload)
    # 1. Test OAuth Handshake
    def test_oauth():
        url = f"{config['host']}/oidc/v1/token"
        data = {"grant_type": "client_credentials", "scope": "all-apis"}
        resp = requests.post(url, data=data, auth=(config['id'], config['secret']), timeout=HTTP_TIMEOUT)
        print("Elapsed (s):", resp.elapsed.total_seconds())
        resp.raise_for_status()
        token_container['token'] = resp.json().get("access_token")
    
    # 2. Test Cluster Access
    def test_cluster():
        url = f"{config['host']}/api/2.0/clusters/get?cluster_id={config['cluster_id']}"
        resp = requests.get(url, headers=headers, timeout=HTTP_TIMEOUT)
        print("Elapsed (s):", resp.elapsed.total_seconds())
        resp.raise_for_status()

    # 3. Test SQL Warehouse & Permissions (Create/Drop)
    def test_sql_permissions():
        # First check Warehouse existence
        url = f"{config['host']}/api/2.0/sql/warehouses/{config['sql_id']}"
        resp = requests.get(url, headers=headers, timeout=HTTP_TIMEOUT)
        print("Elapsed (s):", resp.elapsed.total_seconds())
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
        print("Elapsed (s):", resp.elapsed.total_seconds())
        resp.raise_for_status()
        if resp.json().get('status', {}).get('state') == 'FAILED':
             raise Exception("CREATE TABLE Failed: " + str(resp.json().get('status', {}).get('error')))

        print(f"{GREEN}Successfully created table {test_table}{RESET}")
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

    # 4. Test Forbidden Access (Schema Isolation)
    def test_forbidden():
        # Try to access a schema that should be forbidden.

        # first, see who really calls the query: the user in the PC (probably with admin grants), or the SP
        me_url = f"{config['host']}/api/2.0/preview/scim/v2/Me"
        me = requests.get(me_url, headers=headers, timeout=15)
        print("Elapsed (s):", me.elapsed.total_seconds())
        me.raise_for_status()
        print("Caller:", me.json().get("userName"), "id:", me.json().get("id"))

        # If current schema is schema_01, we try schema_02, otherwise we try schema_01.
        forbidden_schema = "schema_01" if config['schema'] != "schema_01" else "schema_02"

        sql_url = f"{config['host']}/api/2.0/sql/statements"
        query_data = {
            "warehouse_id": config['sql_id'],
            "statement": f"SELECT 1 FROM {config['catalog']}.{forbidden_schema}.test_data LIMIT 1",
            "wait_timeout": "0s"  # return immediately with PENDING; we poll below for the terminal state
        }
        resp = requests.post(sql_url, headers=headers, json=query_data, timeout=15)
        print("Elapsed (s):", resp.elapsed.total_seconds())

        if resp.status_code in [403, 401]:
            return  # Expected: permission denied at the HTTP level

        resp.raise_for_status()

        # Poll until the statement reaches a terminal state (FAILED / SUCCEEDED / CANCELED)
        TERMINAL_STATES = {"SUCCEEDED", "FAILED", "CANCELED", "CLOSED"}
        stmt_id = resp.json().get("statement_id")
        status = resp.json().get("status", {})
        if stmt_id:
            for _ in range(30):
                if status.get("state") in TERMINAL_STATES:
                    break
                time.sleep(1)
                det = requests.get(
                    f"{config['host']}/api/2.0/sql/statements/{stmt_id}",
                    headers=headers, timeout=15
                ).json()
                print("Elapsed (s):", resp.elapsed.total_seconds())
                status = det.get("status", {})

        state = status.get("state")
        if state == "FAILED":
            error_msg = status.get("error", {}).get("message", "")
            # We expect Permission Denied.
            # Sometimes it says 'does not exist' if you don't even have USAGE on the schema.
            if any(err in error_msg for err in ["PERMISSION_DENIED", "does not exist", "Unauthorized", "INSUFFICIENT_PERMISSIONS"]):
                return
            raise Exception(f"Expected permission failure for {forbidden_schema}, but got: {error_msg}")
        elif state == "SUCCEEDED":
            raise Exception(f"Access to {forbidden_schema} should have been DENIED, but it SUCCEEDED.")
        else:
            raise Exception(f"Statement ended in unexpected state '{state}' for {forbidden_schema}.")

    # --- OAuth always runs first (token required for all other tests) ---
    test_step("OAuth Authentication", test_oauth)
    if 'token' not in token_container:
        print(f"{RED}Cannot proceed with other tests without a valid token.{RESET}")
        return
    headers = {"Authorization": f"Bearer {token_container['token']}"}

    # --- Comment out any tests you don't want to run ---
    test_step("Cluster Access",             test_cluster)
    test_step("SQL Warehouse Read/Write",   test_sql_permissions)
    test_step("Forbidden Schema Access",    test_forbidden)

if __name__ == "__main__":
    print("--- Databricks Permission Validator ---")
    run_tests()
    print("---------------------------------------")
