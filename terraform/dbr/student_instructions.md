# Student Instructions: Databricks Project Setup

Welcome! This guide will help you connect your local environment to the Databricks platform and verify your permissions.

## 1. Prerequisites
You should have received a `.env` file containing your group's specific credentials:
- `DATABRICKS_HOST`
- `DATABRICKS_CLIENT_ID`
- `DATABRICKS_CLIENT_SECRET`
- `DATABRICKS_CATALOG`
- `DATABRICKS_SCHEMA`

...and others.

Ensure this file is in the root of your project directory.

## 2. Verify Connection
We have provided a script `test_connection.py` to verify that your credentials work and that you have the correct permissions (Create Table, Access Cluster, etc.).

1. Install dependencies:
   ```bash
   pip install requests python-dotenv
   ```
2. Run the test:
   ```bash
   python test_connection.py
   ```
   **Expected Output:**
   ```
   Testing OAuth Authentication... PASS
   Testing Cluster Access... PASS
   Testing SQL Warehouse Read/Write Access... PASS
   ```

## 3. Manual Job Creation
You have permission to create Databricks Jobs (e.g., to run a scheduled Notebook). 
Since this is a learning exercise, you will create your first job manually:

1. Log in to the Databricks Workspace (URL provided in your `.env`).
2. Navigate to **Workflows** -> **Jobs & Pipelines**.
3. Click **Create Job**.
4. Name it: `job_<your_group_number>_demo` (e.g., `job_01_demo`).
5. **Task Configuration:**
   - **Type:** Notebook
   - **Source:** Workspace
   - **Path:** `/Shared/sample_notebook`
   - **Cluster:** Select your group's cluster (`cluster_01`, etc.).
   - **Parameters:** Add "Base parameters" so the notebook knows which schema to use:
     - `catalog`: (Leave empty to use default)
     - `schema`: `schema_<your_group_number>` (e.g., `schema_01`)
     - `group_name`: `group_<your_group_number>`

  The parameters are needed only if you use the sample_notebook.

6. Click **Create**.
7. Click **Run Now** to verify it works.

## 4. Troubleshooting
- **OAuth Fail:** Check your Client ID/Secret in `.env`.
- **SQL Fail:** Ensure you are using your assigned schema (`schema_01`) and not another group's.
- **Cluster Fail:** Your cluster might be terminated. Go to **Compute** in the UI and start it if necessary.
