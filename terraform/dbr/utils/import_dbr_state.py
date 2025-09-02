# Import the existing Databricks resources into Terraform
# [NC 2025-04-23] 

# Sometimes, the TF state is not in sync with the actual resources in Databricks.
# This script will import the existing Databricks resources into Terraform.
# It will create a new Terraform state file with the imported resources.

"""
How to use this script:
First, [I don't know why], TF requires the user_name key to be present in its state in order to iport it. crazy.

As GPT said:
terraform import only succeeds when both of these are true:

The resource’s address (for example
databricks_user.workspace_user["group_01_michal.kfir@campus.technion.ac.il"])
is present in your configuration ( *.tf files ).

You supply the correct remote-side ID (the SCIM ID).
If either side is missing, Terraform prints “Configuration for import target does not exist” 

Make sure the configuration knows about all users:
  create a CSV contains every [group_name,member_name] pair that Databricks already has

  run 
    tf init
    tf plan

  If everything is covered you should see a + (create) line for each missing user. Do not apply – we are going to import them instead.
"""

import os
import requests

# dry_run = False
# if dry_run:
#     print("This is a dry run. No changes will be made to the Terraform state.")

# read the Databricks token and URL from environment
DATABRICKS_TOKEN = os.environ.get("TF_VAR_databricks_token")
if not DATABRICKS_TOKEN:
    raise ValueError("DATABRICKS_TOKEN environment variable is not set")
if not DATABRICKS_TOKEN.startswith("dapi"):
    raise ValueError("DATABRICKS_TOKEN environment variable is not a Databricks token")

# read the Databricks URL from environment
host_name = os.environ.get("TF_VAR_databricks_host")
if not host_name:
    raise ValueError("DATABRICKS_host environment variable is not set")

DATABRICKS_URL = f"https://{host_name}/api/2.0/preview/scim/v2/"

# Get all users
msg = f"{DATABRICKS_URL}Users"
headers={"Authorization": f"Bearer {DATABRICKS_TOKEN}"}
print(f"Getting users from {msg}, headers {headers}")
response = requests.get(f"{DATABRICKS_URL}Users", headers={"Authorization": f"Bearer {DATABRICKS_TOKEN}"})
users = response.json()["Resources"]

# create TF commands to import existing users
for user in users:
    user_id = user["id"]
    user_name = user["userName"]
    #group_id = user["groups"][0]["value"] if user["groups"] else None
    #group_name = user["groups"][0]["display"] if user["groups"] else None
    #user_to_group[user_name] = group_name

    tf_addr = f'databricks_user.workspace_user["{user_name}"]'
    print(f'terraform import {tf_addr} {user_id}')


# # Get all groups
# response = requests.get(f"{DATABRICKS_URL}Groups", headers={"Authorization": f"Bearer {DATABRICKS_TOKEN}"})
# groups = response.json()["Resources"]

# # Import each group into Terraform
# for group in groups:
#     group_id = group["id"]
#     group_name = group["displayName"]
#     if dry_run:
#         print(f"Would import group {group_name} with ID {group_id}")
#     else:
#         # Check if the group name is valid for Terraform
#         if not group_name.isidentifier():
#             print(f"Group name {group_name} is not a valid Terraform identifier. Skipping import.")
#             continue
#         # Import the group into Terraform
#         # Note: The group name must be a valid Terraform identifier
#         subprocess.run(["terraform", "import", f"databricks_group.{group_name}", group_id])
