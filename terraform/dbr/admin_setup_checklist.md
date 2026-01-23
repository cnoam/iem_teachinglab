# Workspace Admin: Post-Terraform Checklist (30 Groups)

As a Workspace Admin, follow these steps to manually configure permissions and secrets.

**Current Status:**
- ✅ Service Principal creation & Permissions (Automated)
- ✅ SQL Warehouse creation (Automated)
- ⚠️ Service Principal Secrets (Managed via Key Vault - Manual Entry Required)
- ✅ Student Group Data Permissions (Automated - Assigned to individual users)


## 📋 Phase 0: Infrastructure Prep (Key Vault)
*We use Azure Key Vault to securely store SP secrets, allowing Terraform to read them automatically.*

### 1. Create Key Vault
**Why?** To act as a bridge between the manual secret generation (by Admin) and Terraform automation.

As of 2026-01, Creating secrets for Service Principals *using automation* can be done only by Admin account.
Since I have only Workspace admin, we (tech support and me) decided that they generate the secrets, and put them in a vault.
My code will read from the vault and do all the work.

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


## 📋 Phase 1: Authentication (Secret Generation)
*Perform this ONCE per group to populate the Key Vault.*

1.  **Generate & Store Secret:**
    *   Go to **Databricks Settings** -> **Service Principals**.
    *   For `sp_01`, generate a secret.
    *   **Store in Vault:**
        ```bash
        az keyvault secret set --vault-name "sp-secrets-94290" --name "sp-secret-group_01" --value "<PASTE_SECRET_HERE>"
        ```
    *   (Repeat for all 30 groups).

2.  **Generate Student Files:**
    *   Run Terraform (it now reads from KV):
        ```bash
        terraform apply
        terraform output -json sp_credentials_and_env_vars > all_groups.json
        ```
    *   Create files:
        ```bash
        python3 utils/generate_env_files.py
        ```
    *   *Result:* The `.env` files in `dist/student_envs/` now contain the **real** secrets automatically!


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

The files in `dist/student_envs/` (one for each group) should then be distributed to the student groups.


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

