# Migration to Serverless Compute

## Why serverless

Classic all-purpose clusters (used in `../dbr/`) require 3–10 minutes to start and need explicit node-type sizing, autoscaling configuration, and library pre-installation. Databricks serverless compute eliminates all of that:

- **Instant start** (~10 seconds) — no more waiting at the beginning of every lab session.
- **No cluster management** — no `node_type_id`, `min/max_workers`, or `autotermination_minutes`.
- **Unity Catalog native** — serverless requires UC, which enforces proper data isolation.
- **Pay per use** — no idle DBU charges between sessions.

## What changed from `../dbr/`

| Area | `dbr/` (classic) | `dbr-serverless/` |
|---|---|---|
| Compute | One `databricks_cluster` per group | None — students attach notebooks to Serverless in the UI |
| Libraries | `databricks_library` (Maven + PyPI) pre-installed on each cluster | `%pip install` inside notebooks |
| Cluster permissions | `databricks_permissions` (CAN_RESTART per group) | Not needed |
| SP cluster access | `CAN_ATTACH_TO` granted to each SP | Not needed |
| `enable_unified_catalog_isolation` | Optional (default `false`) | Always `true` — serverless requires UC |
| State backend | Azure Storage | Local (`dev.tfstate`) |
| Output | `cluster_ids` map | Removed; `sql_warehouse_id` and `sp_credentials_and_env_vars` remain |

Resources removed: `create_clusters.tf`, `install_libs.tf`, all `databricks_permissions.cluster_permissions` blocks.

Everything else is identical: user provisioning, group membership, UC schemas, SQL warehouse, service principal secrets, and catalog/schema grants.

## Python packages

Serverless compute ships with a large pre-installed bundle (pandas, numpy, matplotlib, scikit-learn, PySpark, and more). For anything beyond that, install at the top of the notebook:

```python
%pip install <package-name>
dbutils.library.restartPython()  # required after %pip
```

Maven/JVM libraries (e.g. `spark-nlp`) are **not supported** on serverless. If a course module requires a JVM library, it must run on a classic cluster.

## What groups still do

Without clusters, per-group groups (`group_01`, etc.) no longer control cluster access. Their remaining roles:

- `allow_cluster_create = false` — prevents students from launching classic clusters.
- Membership chain: students → `group_01` → `all_student_groups`.

The `all_student_groups` group is the active isolation boundary:
- `workspace_access = true` — workspace login.
- `databricks_sql_access = true` — SQL warehouse entitlement.
- `CAN_USE` on the shared SQL warehouse.
- `USE_CATALOG / BROWSE` on the Unity Catalog.

UC schema grants still go to **individual student emails** (not groups) because Unity Catalog cannot resolve workspace-local groups. This is unchanged from `dbr/` and is documented in `CLAUDE.md`.

## How to apply

Before the first `terraform apply` each semester, also do (both are one-time/per-semester Azure-side steps,
not managed by this Terraform project):
- **Entra role assignment for student login** -- see `../dbr/readme.md`, "Adding Azure Role Assignments to
  students". This is unchanged by the serverless migration (same Entra SSO login regardless of compute
  mode) but is only documented in the `dbr/` project. Watch for the PIM Eligible-vs-Active pitfall called
  out there.
- **Shared course dataset RBAC**, if deploying against a new storage account for the first time -- see
  `../docs/course_data_storage_setup.md`, step 1 (Azure RBAC on the access connector). Not needed again once
  done for a given storage account.

```bash
cd terraform/dbr-serverless

# First time only
terraform workspace new dev
terraform init

# Every semester
terraform plan
terraform apply
```

Students open Databricks, create or open a notebook, and select **Serverless** from the cluster dropdown — no further setup needed.

Before real students start, run through `docs/student_verification_checklist.md` with a test user.

## Manual step: cap runaway execution time (do this once, before students start)

Classic clusters (`../dbr/`) had a bespoke uptime monitor that forcibly powers off a cluster left running
too long by buggy/runaway student code (not idle time -- autotermination already handles idling). Serverless
has no equivalent uptime-monitor hook, but it does have its own native safeguard: the **Serverless
interactive execution timeout**, which cancels a query/command once it has run continuously for longer than
the configured limit (default 2.5 hours / 9000s).

This is **workspace-level, one setting for the whole workspace** -- it is not per-group and does not need to
be set per course/semester the way `group_XX` resources do. There is currently no Terraform resource or
documented API for it (checked `databricks_workspace_conf`, `databricks_workspace_setting_v2`, and the live
`settings-metadata` endpoint -- none expose it), so it must be set manually, once, per workspace:

1. In the workspace, open the admin console.
2. Go to **Settings > Compute**.
3. Under **Serverless interactive**, set **Serverless interactive execution timeout** to a value shorter than
   the 2.5h default (e.g. 30-60 min, matching the tolerance the old cluster uptime-monitor used).

A student can still lower (but not raise beyond the workspace limit) the timeout for their own notebook via
`spark.databricks.execution.timeout`, but that's opt-in and doesn't weaken the workspace-wide cap.

## Limitations and known issues

- **Maven libraries**: not supported on serverless. Keep `../dbr/` available for NLP or other JVM-dependent exercises.
- **Per-group compute isolation**: classic clusters gave each group a private execution environment. Serverless uses a shared pool with session-level isolation enforced by Unity Catalog. For most teaching scenarios this is sufficient.
- **UC group grants**: workspace-local groups are invisible to UC. If Databricks account-admin rights become available, migrate groups to account-level groups and replace the per-email grant workaround with per-group grants.
