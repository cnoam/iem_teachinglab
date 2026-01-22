# 2026-01-01
# Run this script ONCE in a Databricks workspace to create an isolated "database" for 
# each student group.
#
# All "databases", 'schema' in DBR speak are in a single catalog, whose name is the DBR workspace name

it does not work because the groups are ws level but are expected to be account level


from databricks import sql

# Configuration

# Catalog name is the same as Databricks workspace name
CATALOG = "lab94290w3"

# how many student groups? group_01 .. group_NN
NUM_GROUPS = 32

# Workspace ID (the first part in the URL of the ws)
WS_ID = "adb-983293358114278.18"

# Token (Pesonal Access Token) you created in the portal
TOKEN = "dapi***"
GROUPS = [f"group_{i:02d}" for i in range(1, NUM_GROUPS)]
GROUPS = ['group_26']
HOSTNAME = f"{WS_ID}.azuredatabricks.net"

# To find the URL, select the SQL workspace you created, choose "Connection Details" tab,
# and there you will see both hostname and HTTP path.
HTTP_PATH = f"/sql/1.0/warehouses/44e60e83178ee82c"

def setup_lab():
    with sql.connect(server_hostname=HOSTNAME, http_path=HTTP_PATH, access_token=TOKEN) as conn:
        with conn.cursor() as cursor:
            for group in GROUPS:
                schema = f"{CATALOG}.{group}"
                print(f"Provisioning {schema}...")
                
                # Create isolated schema
                cursor.execute(f"CREATE SCHEMA IF NOT EXISTS {schema}")
                
                # Grant minimal catalog visibility
                cursor.execute(f"GRANT USE CATALOG ON CATALOG `{CATALOG}` TO `{group}`")
                
                # Grant full CRUD permissions within their own schema ONLY
                cursor.execute(f"GRANT USE SCHEMA, CREATE TABLE, SELECT, MODIFY ON SCHEMA {schema} TO `{group}`")

setup_lab()