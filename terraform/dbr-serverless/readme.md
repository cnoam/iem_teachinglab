# Deploying a new course -- Serverless Databricks
*Updated: 2026-11-05*

Default deployment for new semesters. Students use Serverless compute (no clusters).
Need Maven/JVM libraries (e.g. `spark-nlp`)? Use `../dbr/` instead. Background: `MIGRATION.md`.
Install terraform, databricks CLI and az CLI as described in `../dbr/readme.md` ("Installation").

## Checklist

**Workspace & auth**
- [ ] Create the Databricks workspace in the Azure portal (with Unity Catalog; same region as the course storage).
- [x] `databricks auth login --host adb-<id>.<n>.azuredatabricks.net` -> creates a profile in `~/.databrickscfg`.
- [ ] Verify identity: `databricks current-user me --profile <profile>`.

**Terraform config**
- [x] `tf init`, then `tf workspace new <name>` (or `tf workspace select <name>`).
- [x] In `terraform.tfvars`:
  - `workspace_profiles` -- map the TF workspace name to the DBR profile (`safety.tf` blocks unmapped workspaces).
  - `catalog_name` -- an existing UC catalog (`databricks catalogs list`).
  - `course_data_*` -- storage account, containers, access connector ID (Azure RBAC prerequisites: `../docs/course_data_storage_setup.md`).

**Students**
- [x] Export "Students create groups" CSV from Moodle, then
  `python ../convert_moodle_to_tf_format.py <csv>` -> `users.csv` (one row per group, emails only).

**Deploy**
- [x] `tf plan` -- sanity check the plan.
- [x] `tf apply` -- creates users, groups, UC schemas, SQL warehouse, SP secrets, course-data volumes and grants.

**Manual, once per workspace**
- [x] Admin console -> Settings -> Compute -> **Serverless interactive execution timeout**: set to 30-60 min (no TF/API for this).
- [x] Azure role assignment for the course Entra group: **Reader** on the resource group *containing the workspace*,
  assignment type **Active + Time bound** (not PIM Eligible!). Same for the test user `efratsupp@technion.ac.il`.
  Details: `../dbr/readme.md`, "Adding Azure Role Assignments to students".

**Verify**
- [x] Run `docs/student_verification_checklist.md` with the test user.
- [ ] Optional: quota monitor -- see `../../dbr_admin/`.

## Updating during the semester
Edit `users.csv` (or `terraform.tfvars`) and `tf apply` again. Group numbers come from **row order** --
append new groups at the end, never reorder/delete rows in the middle.

## Notes
- State is local (`terraform.tfstate.d/<tf-workspace>/dev.tfstate`, git-ignored) -- back it up.
- UC grants go to individual student emails (workspace-local groups don't resolve in UC).
- `admin_warehouse.tf` creates an admin-only warehouse for `dbr_admin`'s billing and GPU-alert checks
  (they stop it after each query). Never grant students access to it. ID: `tf output admin_checks_warehouse_id`.
- **External apps / service principals**: students may write apps (on a laptop or VM) that connect to
  Databricks, e.g. SQL queries via the shared warehouse. Each group gets a service principal (`sp_NN`)
  limited to its own schema. Hand each group its credentials from
  `tf output -json sp_credentials_and_env_vars` (sensitive -- send privately, per group).
  Secrets expire 180 days after `tf apply` (`lifetime` in `modules/unified_catalog_setup/service_principals.tf`)
  -- make sure that outlasts the semester; renew with `tf apply -replace=<secret resource>`.
- Troubleshooting (state lock, workspace mismatch, auth, Reader-but-no-access): `../dbr/readme.md`, "Troubleshooting".
