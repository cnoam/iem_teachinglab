# Preparing external access to Databricks workspace

The baseline scripts generate clusters and associated groups.

In some use cases, the teacher wants to give students access from web server (external to the Databricks workspace) to resource inside the workspace.

This memo describes the steps to accomplish it.

*as an example, we assume there are 30 groups*

if `enable_unified_catalog_isolation` in terraform.tfvars is set to `true`, the successful completion of the steps will create in the workspace:
- SQL warehouse
- For each group
  - Service Principal and its secret
  - schema
  - sample notebook
  - sample table in the schema
  - sample job to run the notebook and get data from the table.
  - all the needed permissions to use these sample objects.

<br><br>

As a Workspace Admin, follow these steps to manually configure permissions and secrets.

**Current Status:**
- ✅ Service Principal creation & Permissions (Automated)
- ✅ SQL Warehouse creation (Automated)
- ⚠️ Service Principal Secrets (Managed via Key Vault - Manual Entry Required)
- ✅ Student Group Data Permissions (Automated - Assigned to individual users)

## Prerequisites
- You have DataBricks Workspace Admin privileges.
- `az cli` installed, and you are logged in with account that have needed permissions (TBD)
- `databricks cli` is installed
- the config for the affected Databricks workspace exists and is selected in `databricks auth login --profile THE_PROFILE`


## 📋 Phase 0: Infrastructure Prep (Key Vault)
*We use Azure Key Vault to securely store SP secrets, allowing Terraform to read them automatically.*

### 1. Create Key Vault
**Why?** To act as a bridge between the manual secret generation (by Admin) and Terraform automation.

As of 2026-01, Creating secrets for Service Principals *using automation* can be done only by Admin account.

See [explanation](#annex-a-on-creating-secrets)


*   **CLI:**
    ```bash
    az keyvault create --name "sp-secrets-94290" --resource-group "databricks-rg-2025" --location "eastus" --enable-rbac-authorization
    ```
*   **UI:** Search "Key Vaults" -> Create -> Select Subscription/RG -> Name: `sp-secrets-94290` -> Access configuration: "Azure role-based access control".

### 2. Grant Access (RBAC)
**Why?** You (and Terraform) need permission to Read/Write secrets. The "Owner" role is NOT enough for data plane operations.

*   **CLI:**
    ```bash
    # Get your Object ID
    MY_OID=$(az ad signed-in-user show --query id -o tsv) 
    
    # Grant "Key Vault Secrets Officer" (Read/Write)
    az role assignment create \
      --role "Key Vault Secrets Officer" \
      --assignee-object-id "$MY_OID" \
      --scope "/subscriptions/<YOUR_SUB_ID>/resourceGroups/databricks-rg-2025/providers/Microsoft.KeyVault/vaults/sp-secrets-94290"
    ```
*   **UI:** Go to Key Vault -> **Access control (IAM)** -> **Add role assignment** -> Select **"Key Vault Secrets Officer"** -> Assign access to **User** -> Select yourself.


## 📋 Phase 1: Secret Generation


**Generate & Store Secret:**

*   Go to **Databricks Settings** -> **Service Principals**.
*   For `sp_01`, generate a secret.
*   Save the secret in a new row in a `secrets.csv`

File format: 

```csv 
group_number,secret_value
2     01,dapi-xxxxxxxxxxxxxxxxxxxxxxxx
3     02,dapi-yyyyyyyyyyyyyyyyyyyyyyyy
```

*Perform this ONCE per group to populate the Key Vault.*
    
**Store in Vault:** 

Run `utils\populate_secrets_from_csv.sh [--overwrite] secrets.csv`

⚠️ and remember to `rm secrets.csv`
      



## 📋 Phase 2: Verify Group Entitlements (Bypassing UI Hiding)
*Required for students to use the SQL Warehouse UI.*

1.  Go to **Settings** > **Identity** > **Groups**.
2.  Select `group_01`.
3.  Verify that **Databricks SQL Access** is checked.
    *   *Note:* Terraform enables this on the parent group `all_student_groups`. It should inherit, but it is good to verify.


## 📋 Phase 3: Verify SQL Warehouse Permissions (Inheritance Check)
*Terraform granted `CAN_USE` to `all_student_groups` and specific Service Principals.*

1.  Navigate to **SQL Warehouses** -> **"Shared Student Warehouse"** -> **Permissions**.
2.  Verify `all_student_groups` has **Can Use**.


## 📋 Phase 4: Post-Terraform Execution
After the `tf apply` completed successfully, run:

```bash
# 1. Export env vars (including sensitive secrets from KeyVault) to a JSON file
terraform output -json sp_credentials_and_env_vars > all_groups.json

# 2. Use all_groups.json to generate .env file for each group in dist/student_envs/
python utils/generate_env_files.py

# 3. Create initial tables for each of the groups (Requires databricks-sql-connector)
python utils/seed_tables.py
```
> ⚠️ WARNING: `all_groups.json` contains secrets.
> 
The files in `dist/student_envs/` (one for each group) should then be distributed to the student groups. Each group has its own file. These file contains **secret** for that group.


## 📋 Phase 5: Verification
1.  **Run the Test:**
    ```bash
    export $(grep -v '^#' dist/student_envs/group_01.env | xargs)
    python3 test_connection.py
    ```
2.  **Success Criteria:**
    - `OAuth Authentication... PASS`
    - `Cluster Access... PASS`
    - `SQL Warehouse Read/Write Access... PASS`


<hr>

# 📋 Teardown
To remove the Warehouse/schema/servicePrincipal/jobs,<br>
change `enable_unified_catalog_isolation` to **`false`** in terraform.tfvars.

Before running *tf apply* we need to undo the `seed_tables.py`

Remove **ALL** tables in the schemas (also those created by students!) by running

```bash 
cd dbr
source utils/venv/bin/activate # so we have the needed package
#from dbr/dist/student_env/group*.env copy the needed vars:
export DATABRICKS_SQL_ID=24a8ab8d4dfa079d
export DATABRICKS_HOST=https://adb-7405617061350271.11.azuredatabricks.net

# generate PAT (e.g. in the UI) and save here (or pass via `--token`)
export DATABRICKS_TOKEN=***
python utils/cleanup_schemas.py --catalog 94290_dev
deactivate
```


After successful deletion of the schemas, run `tf apply`


<hr>

# Annex A: On creating secrets

On 2026-01-28 I (cnoam) talked with Lior S, who is responsible for MS infra in the Technion. We discussed who should generate the SP secrets.

My understanding was that an Account Admin (i.e. Lior) will generate the 30 secrets (one per SP), using a script (I can provide the script). He will place these secrets in a vault, and my script will pull these secrets during `terraform apply`

However, he said that:
- he is not familiar enough with DBR
- generating secrets is risky due to possible leakage, so he do not want to use a script. Rather, do it manually.

Since the generation is manual, I can do it mayself using the GUI and simply copy paste 30 times into a temp file. that file will be read by a script that will insert the secrets into the vault.

We concluded that the latter is the way we use for now.

I don't like it very much due to the manual labor, but we don't have a workaround.
