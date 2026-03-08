# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

> This file is scoped to the `dbr/` subdirectory. The parent `terraform/CLAUDE.md` covers the overall repo and common commands — read it first.

## File Map

| File | Purpose |
|---|---|
| `main.tf` | Provider config, backend, CSV parsing into `local.groups` / `local.group_configs` / `local.group_members_flattened` |
| `variables.tf` | Cluster / library / profile variables |
| `variables_UCatalog.tf` | `enable_unified_catalog_isolation`, `catalog_name`, `sql_warehouse_name` |
| `keyvault.tf` | Fully commented out — KV approach replaced by auto-generated secrets |
| `uc_module.tf` | Instantiates `modules/unified_catalog_setup` when `enable_unified_catalog_isolation=true` |
| `safety.tf` | Aborts if current TF workspace is not in `workspace_profiles` |
| `create_clusters.tf` | One Databricks cluster per group |
| `create_objects.tf` | Users and workspace-local groups |
| `assign_groups.tf` | User → group membership |
| `install_libs.tf` | Maven + Python library installation (requires running clusters) |
| `jobs.tf` | Per-group Databricks Jobs |
| `create_notebook.tf` | Notebook provisioning |
| `outputs.tf` | `cluster_ids`, `sql_warehouse_id` |

UC-related resources (`service_principals`, `schemas`, `sql_warehouse`, grants, secrets) live in **`modules/unified_catalog_setup/`**. The sensitive `sp_credentials_and_env_vars` output (per-group `.env` vars for the Flask Proxy) is in `modules/unified_catalog_setup/outputs.tf`.

## Unity Catalog (UC) Feature Flag

Everything UC-related is gated on `var.enable_unified_catalog_isolation` (default `false`), via `uc_module.tf` which uses `count = ... ? 1 : 0`. When `false`, only clusters/users/groups/libs are provisioned.

## Service Principal & Secret Flow (Current — Automatic)

Implemented in `modules/unified_catalog_setup/`:

1. **SP creation** — `databricks_service_principal.group_sps` (in `main.tf`) creates one SP per group.
2. **Secret creation** — `databricks_service_principal_secret.group_sp_secrets` (in `service_principals.tf`) auto-generates a secret per SP with `lifetime = "1814400s"` (21 days).
3. **Output** — `sp_credentials_and_env_vars` (sensitive, in `outputs.tf`) emits all per-group env vars including `DATABRICKS_CLIENT_SECRET` read directly from the generated secret.

**Secret rotation**: `lifetime` sets how long each secret lives. Rotation requires running `tf apply` before expiry — automate with a scheduled pipeline. Key Vault is no longer used.

**Known limitation**: Unity Catalog cannot resolve workspace-local groups, so schema/catalog grants are given to **individual student emails** (iterated from CSV), not to groups.

## Key Pitfalls

- **`databricks_permissions` is authoritative** — declare it exactly once per object type. Multiple declarations cause endless ping-pong between applies (documented in `service_principals.tf`).
- **`databricks_grants` is also authoritative** — the catalog grant resource uses `dynamic` blocks to merge all principals into a single resource for this reason.
- **`main.tf` has a hardcoded subscription ID** — the `azurerm` provider block contains a `# BUG hardcoded value` comment; update it per deployment.
- **`catalog_name` default is hardcoded** — `94290_dev` in `variables_UCatalog.tf`; override in `.tfvars` per course.
- **Backend is set to local** in the committed `main.tf` — switch to the commented `azurerm` backend block for production use.
