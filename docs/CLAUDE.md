# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a teaching lab administration system for Technion's Faculty of Data and Decisions. It automates provisioning and management of Databricks clusters for student courses by:
- Creating Databricks clusters/users/groups based on Moodle group assignments
- Enforcing daily cluster uptime quotas to control cloud costs
- Sending quota warning/termination notifications via Azure email service
- Running daily reports and resetting quotas at midnight

The system combines Infrastructure-as-Code (Terraform) for initial deployment with Python polling for continuous quota enforcement.

## Development Commands

### Python Setup (Databricks module)
```bash
cd databricks
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Testing
```bash
# Run all tests
pytest tests/

# Run with verbose output
pytest -v tests/

# Run specific test file
pytest tests/test_scheduling.py
```

### Running Python Modules
The codebase uses Python module-style execution via the `-m` flag:
```bash
# Periodic quota polling (normally via cron)
python -m databricks.poll_clusters

# End-of-day operations (normally via cron)
python -m databricks.end_of_day_operations

# CLI tool for management
python -m databricks.main --print_clusters
python -m databricks.main --print_user_groups
python -m databricks.main --test_email
python -m databricks.main --cluster_usage
python -m databricks.main --create_from_csv path/to/moodle.csv
python -m databricks.main --delete_all_users
```

### Terraform Deployment
```bash
cd terraform/dbr

# Export environment variables (modify create_vars.sh with your credentials)
source ../create_vars.sh

# Initialize Terraform
terraform init

# Check deployment plan
terraform plan

# Deploy with parallel execution (recommended, 50x faster)
terraform apply -parallelism=50

# Two-phase deployment (needed if cluster setup times out):
terraform apply --target=null_resource.force_creation -parallelism=50
terraform apply -parallelism=50

# Destroy resources
terraform destroy

# Debug deployment
TF_LOG=DEBUG terraform apply --target=null_resource.force_creation
```

### Linting & Code Quality
```bash
# Dead code elimination
pip install vulture
vulture databricks/ --exclude "*/tests/*,*/venv/*,*/docs/*"
# To silence warnings, add `# noqa: vul` at first line of function
```

### Moodle Data Conversion
```bash
# Convert Moodle CSV to Terraform format
cd terraform
python convert_moodle_to_tf_format.py path/to/moodle_groups.csv
# Output: terraform/dbr/users.csv
```

### Backup & Restoration
```bash
# Export all student notebooks for backup
cd databricks/scripts
# Set DATABRICKS_HOST and DATABRICKS_TOKEN first
./export_notebooks.sh

# Import/restore notebooks
./import_dbr_workspaces.sh
./import_per_user.sh
```

## Architecture & Key Components

### Directory Structure
- **`databricks/`** - Core Python application
  - `database/` - Peewee ORM models (ClusterUptime, ClusterCumulativeUptime, ClusterInfo)
  - `resource_manager/` - Uptime tracking, statistics, Azure email utilities
  - `tests/` - Unit tests (pytest-based)
  - `scripts/` - Notebook export/import utilities
  - `DataBricksClusterOps.py` - Cluster creation/deletion/permission APIs
  - `DataBricksGroups.py` - User/group management
  - `MoodleFileParser.py` - CSV parsing from Moodle
  - `poll_clusters.py` - Entry point for quota polling (cron-driven)
  - `end_of_day_operations.py` - Entry point for daily reset/reporting (cron-driven)
  - `main.py` - CLI interface for manual operations

- **`terraform/dbr/`** - Infrastructure as Code
  - `main.tf` - Provider config and Azure backend setup
  - `create_objects.tf` - User and group resource definitions
  - `create_clusters.tf` - Cluster resource definitions
  - `assign_groups.tf` - Permission assignments
  - `install_libs.tf` - JAR and Python package installation
  - `terraform.tfvars` - Variable definitions (cluster specs, library versions)
  - `users.csv` - Converted user/group data from Moodle

### Quota Enforcement Model
- Each cluster has a daily uptime limit (e.g., 480 minutes)
- Polling runs every 15 minutes, tracking cumulative uptime
- When cluster reaches soft quota: warning email sent
- When cluster exceeds hard quota: cluster terminated + notification sent
- At midnight: counters reset, usage archived to history table, permissions restored

### Database Design
SQLite database (`cluster_uptimes.db`) with Peewee ORM:
- **ClusterUptime** - Current session uptime (refreshed during polling)
- **ClusterCumulativeUptime** - Daily cumulative totals
- **ClusterInfo** - Cluster metadata (ID, name, quota, creator)

### Environment Configuration
Create `.env` file in `databricks/` directory:
```
DATABRICKS_HOST=https://adb-xxxx.azuredatabricks.net
DATABRICKS_TOKEN=dapi...
AZURE_EMAIL_ACCESS_KEY=...
ADMIN_EMAIL=admin@example.com
REPORT_RECIPIENT_EMAIL=reports@example.com
DATABRICKS_MAX_UPTIME=480  # Hard quota in minutes
DATABRICKS_WARN_UPTIME=400 # Soft quota for warnings
```

### Terraform Environment Variables
Required for `terraform apply`:
```bash
export TF_VAR_databricks_host=https://adb-xxxx.azuredatabricks.net
export TF_VAR_databricks_token=dapi...
```

Set once in `terraform/create_vars.sh` then `source ../create_vars.sh`.

## Production Deployment (Cron-based Monitoring)

The quota enforcement runs on an Azure VM with these cron jobs:

```bash
# Every 15 minutes (quota polling)
*/15 * * * * /home/azureuser/periodic_poll.sh 2>&1 | systemd-cat -t dbr_scripts

# Every midnight + 7 min (daily reset/reporting)
7 0 * * * /home/azureuser/end_of_day_ops.sh 2>&1 | systemd-cat -t dbr_scripts
```

Wrapper scripts:
```bash
# periodic_poll.sh
#!/bin/bash -eu
logger -t dbr_scripts Periodic Poll starting
cd /home/azureuser/iem_teachinglab
source databricks/venv/bin/activate
timeout 30 python -m databricks.poll_clusters
deactivate

# end_of_day_ops.sh
#!/bin/bash -eu
logger -t dbr_scripts EndOfDay starting
cd /home/azureuser/iem_teachinglab
source databricks/venv/bin/activate
python -m databricks.end_of_day_operations
deactivate
```

View logs: `journalctl -t dbr_scripts -r` (latest first)

## Testing Procedures

### Email System
```bash
# Test email delivery
python -m databricks.main --test_email
# Verify you received an email

# Verify end-of-day operations
python -m databricks.end_of_day_operations
# Should send usage report email
```

### Cron Execution
1. Copy periodic_poll cron line, change time to 2 minutes ahead
2. Verify output: `journalctl -t dbr_scripts` and check for warning emails
3. Delete test cron job
4. Verify nightly end_of_day_ops sends usage report

### Workspace Verification
```bash
# After Terraform deployment:
python -m databricks.main --print_clusters    # See all clusters
python -m databricks.main --print_user_groups # See users/groups
python -m databricks.main --cluster_usage     # Current uptime stats
```

## Key Configuration Points

### Cluster Auto-Termination
Databricks has default 30-day inactivity termination. See: https://kb.databricks.com/en_US/clusters/pin-cluster-configurations-using-the-api

### Terraform Installation Dependencies
- Must run `terraform apply --target=null_resource.force_creation` first (creates clusters)
- Then `terraform apply` to install libraries (clusters must be running)
- Library installation timeout: increase cluster startup time if needed

### State Management
Terraform state stored remotely in Azure Storage Account (managed backend).

For local development:
```bash
terraform state pull > dev.tfstate
# Edit main.tf to use local backend
terraform init -reconfigure
# Work as usual
# When done, restore remote backend and:
terraform init -reconfigure -migrate-state
```

### Azure Storage for Backup Data
Cold storage account: `ddsteachinglabdatastg` (ADLS Gen2) for cost reduction.

## Important Notes

### Cost Warnings
- Databricks workspace costs ~$700/month just being idle (as of 2025-04-25)
- Delete workspace + associated storage account at semester end
- Students cannot create additional clusters (disabled in workspace)

### Database Mutations
- `end_of_day_operations.py` deletes old daily records before archiving new ones
- Ensure this runs correctly; verify database hasn't grown unexpectedly

### Moodle CSV Format
- Remove "..." header line before processing
- Replace non-English group names
- One row per user, one column per group (groups are email lists)
- Run through `convert_moodle_to_tf_format.py` before Terraform

### Databricks CLI Limitations
- Credentials from `~/.databrickscfg` can interfere with env vars
- If auth fails: run `terraform init` to refresh provider config
- Use `az login` to ensure correct Azure subscription for Terraform state

### Workspace Timeouts
Library installation may timeout if cluster not fully ready. Workaround:
- Wait a few minutes for cluster to stabilize
- Run `terraform apply` again
- Last resort: `terraform state rm` to reset state file

## Debugging

### Terraform Dependency Graph
```bash
terraform graph > graph.dot && dot -Tpng graph.dot -o graph.png
```

### Check Resource Status
```bash
terraform state list
terraform state show <resource_type.resource_name>
```

### Force Unlock (if state locked by failed apply)
```bash
terraform force-unlock -force <LOCK-ID>
```

### Refresh State After Manual Changes
```bash
terraform apply -refresh-only
```

## Recent Changes & Known Issues

- Email system uses Azure Communication Services (Gmail/Mailjet no longer viable)
- Converted legacy Python scripts to proper Python modules (`-m` style execution)
- Fixed daily record deletion bug that caused database bloat
- Fixed timing calculations for quota enforcement
- Database access and session handling improvements
