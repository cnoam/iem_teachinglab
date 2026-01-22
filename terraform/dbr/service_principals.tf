#
# Service Principals
#
# Creates a Service Principal for each student group to be used by the Flask Proxy.
#

resource "databricks_service_principal" "group_sps" {
  for_each = var.enable_unified_catalog_isolation ? local.group_configs : {}

  display_name = each.value.service_principal_name
  active       = true
}

#
# Service Principal Secrets
#
# Generates a secret for each SP. 
# WARNING: The secret value will be stored in the Terraform state.
#
# AUTOMATION FAILED: Your workspace requires Account Admin privileges to automate secret generation.
# Secrets must be created manually via the UI as per admin_setup_checklist.md.
#
# resource "databricks_service_principal_secret" "group_sp_secrets" {
#    for_each = var.enable_unified_catalog_isolation ? local.group_configs : {}
# 
#   service_principal_id = databricks_service_principal.group_sps[each.key].id
# }

#
# Grants for Service Principals
#

# Grant SP access to the Shared SQL Warehouse
# the "databricks_permissions" is authoritative, so we 
# must have a single resource (not accurate!).
# 
# Terraform will NOT alert you if you declare more,
# but this will cause endless ping-pong: each apply call, 
# one resource will be happy, and the other will not, so wil
# modify the state, causing the first resource to become in state "need update"
resource "databricks_permissions" "warehouse_usage" {
  count = var.enable_unified_catalog_isolation ? 1 : 0

  sql_endpoint_id = databricks_sql_endpoint.shared_warehouse[0].id

  access_control {
    group_name       = databricks_group.all_student_groups.display_name
    permission_level = "CAN_USE"
  }

  dynamic "access_control" {
    for_each = databricks_service_principal.group_sps
    content {
      service_principal_name = access_control.value.application_id
      permission_level       = "CAN_USE"
    }
  }
}


# Grant SP and student_groups  access to their specific Schema
resource "databricks_grants" "schema_grants" {
  for_each = var.enable_unified_catalog_isolation ? local.group_configs : {}

  schema = databricks_schema.group_schemas[each.key].id

  # matching SP
  grant {
    principal  = databricks_service_principal.group_sps[each.key].application_id
    privileges = ["USE_SCHEMA", "CREATE_TABLE", "SELECT"]
  }

  # 
  # Grant Access to Individual Students
  #
  # WORKAROUND EXPLANATION:
  # Unity Catalog cannot see Workspace-Local groups (like 'group_01'), causing "Principal does not exist" errors.
  # Account-Level groups are required for UC, but we don't have Account Admin rights to create them.
  # So, we are forced to grant permissions to EACH STUDENT INDIVIDUALLY by iterating over the CSV data.
  #
  dynamic "grant" {
    # local.groups is the raw CSV list-of-lists. 
    # each.value.index corresponds to the row number (0 for group_01, etc.)
    for_each = [for m in local.groups[each.value.index] : trimspace(m) if trimspace(m) != ""]

    content {
      principal = grant.value # This is the student email
      privileges = [
        # "BROWSE",    # BROWSE is not a valid privilege on Schemas in this metastore version.
        "USE_SCHEMA",
        "CREATE_TABLE",
        "SELECT",
        "MODIFY", # inserts/updates/deletes
      ]
    }
  }

  depends_on = [
    databricks_group.student_groups,
    databricks_grants.catalog_grants,
    databricks_user.workspace_user # Ensure users exist before granting
  ]
}

# Grant access to the Catalog
# This resource must be executed ONCE for all resources that use this single catalog.
# Each run is authoritative, meaning it will overwrite the previous one.
# This is why I add "dynamic"
resource "databricks_grants" "catalog_grants" {
  count   = var.enable_unified_catalog_isolation ? 1 : 0
  catalog = var.catalog_name

  grant {
    principal  = databricks_group.all_student_groups.display_name
    privileges = ["USE_CATALOG", "BROWSE"]
  }


  dynamic "grant" {
    for_each = databricks_service_principal.group_sps
    content {
      principal  = grant.value.application_id
      privileges = ["USE_CATALOG"]
    }
  }

  # Grant explicit BROWSE to each student to bypass group inheritance issues in the UI
  dynamic "grant" {
    for_each = toset([for m in local.group_members_flattened : m.member_name])
    content {
      principal  = grant.value # Student email
      privileges = ["USE_CATALOG", "BROWSE"]
    }
  }
}

#
# Fetch Secrets from Key Vault
#
# Assumes secrets are named: sp-secret-group-01, sp-secret-group-02, etc.
#
data "azurerm_key_vault_secret" "sp_secrets" {
  for_each = var.enable_unified_catalog_isolation ? local.group_configs : {}
  # key name cannot contain "_"
  name         = "sp-secret-${replace(each.value.group_name, "_", "-")}" # e.g. sp-secret-group-01
  key_vault_id = data.azurerm_key_vault.vault.id
}

#
# Outputs for .env generation
#
output "sp_credentials_and_env_vars" {
  value = {
    for k, v in local.group_configs : k => { # k will be "01", "02", etc.
      DATABRICKS_CLIENT_ID     = try(databricks_service_principal.group_sps[k].application_id, "")
      DATABRICKS_CLIENT_SECRET = try(data.azurerm_key_vault_secret.sp_secrets[k].value, "SECRET_NOT_FOUND_IN_KV")
      DATABRICKS_HOST          = data.databricks_current_config.this.host
      DATABRICKS_SQL_ID        = var.enable_unified_catalog_isolation ? databricks_sql_endpoint.shared_warehouse[0].id : ""
      DATABRICKS_CLUSTER_ID    = try(databricks_cluster.clusters[k].id, "")
      DATABRICKS_CATALOG       = var.catalog_name
      DATABRICKS_SCHEMA        = v.schema_name
      DATABRICKS_SP_NAME       = v.service_principal_name
      DATABRICKS_GROUP_NAME    = v.group_name
      DATABRICKS_CLUSTER_NAME  = v.cluster_name
    }
  }
  sensitive = true
}
