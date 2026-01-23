terraform {
  required_providers {
    databricks = {
      source = "databricks/databricks"
    }
    azurerm = {
      source = "hashicorp/azurerm"
    }
  }
}

#
# Jobs
#
resource "databricks_job" "group_jobs" {
  for_each = var.group_configs

  name = each.value.job_name

  task {
    task_key = "run_notebook"
    notebook_task {
      notebook_path = "/Shared/sample_notebook"
      base_parameters = {
        "group_name" = each.value.group_name
        catalog      = var.catalog_name
        schema       = databricks_schema.group_schemas[each.key].name
      }
    }
  }
}

resource "databricks_permissions" "sp_job_permissions" {
  for_each = var.group_configs

  job_id = databricks_job.group_jobs[each.key].id

  access_control {
    service_principal_name = databricks_service_principal.group_sps[each.key].application_id
    permission_level       = "CAN_MANAGE_RUN"
  }
}

#
# Service Principals
#
resource "databricks_service_principal" "group_sps" {
  for_each = var.group_configs

  display_name = each.value.service_principal_name
  active       = true
}

#
# SQL Warehouse (Shared)
#
resource "databricks_sql_endpoint" "shared_warehouse" {
  name             = var.sql_warehouse_name
  cluster_size     = "2X-Small"
  max_num_clusters = 1
  auto_stop_mins   = 10
  warehouse_type   = "PRO"
}

#
# Schemas (Unity Catalog)
#
resource "databricks_schema" "group_schemas" {
  for_each = var.group_configs

  catalog_name = var.catalog_name
  name         = each.value.schema_name
  comment      = "Dedicated schema for ${each.value.schema_name}"
}

#
# Grants
#

# Warehouse Usage
resource "databricks_permissions" "warehouse_usage" {
  sql_endpoint_id = databricks_sql_endpoint.shared_warehouse.id

  access_control {
    group_name       = var.all_student_groups_name
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

# Schema Grants
resource "databricks_grants" "schema_grants" {
  for_each = var.group_configs

  schema = databricks_schema.group_schemas[each.key].id

  # Matching SP
  grant {
    principal  = databricks_service_principal.group_sps[each.key].application_id
    privileges = ["USE_SCHEMA", "CREATE_TABLE", "SELECT"]
  }

  # Individual Students
  dynamic "grant" {
    for_each = [for m in var.student_groups_csv_rows[each.value.index] : trimspace(m) if trimspace(m) != ""]

    content {
      principal = grant.value
      privileges = [
        "USE_SCHEMA",
        "CREATE_TABLE",
        "SELECT",
        "MODIFY",
      ]
    }
  }
  
  depends_on = [
     databricks_grants.catalog_grants
  ]
}

# Catalog Grants
resource "databricks_grants" "catalog_grants" {
  catalog = var.catalog_name

  grant {
    principal  = var.all_student_groups_name
    privileges = ["USE_CATALOG", "BROWSE"]
  }

  dynamic "grant" {
    for_each = databricks_service_principal.group_sps
    content {
      principal  = grant.value.application_id
      privileges = ["USE_CATALOG"]
    }
  }

  # Individual BROWSE
  dynamic "grant" {
    for_each = toset([for m in var.group_members_flattened : m.member_name])
    content {
      principal  = grant.value
      privileges = ["USE_CATALOG", "BROWSE"]
    }
  }
}

#
# Secrets (Azure Key Vault)
#
data "azurerm_key_vault" "vault" {
  name                = var.key_vault_name
  resource_group_name = var.key_vault_rg
}

data "azurerm_key_vault_secret" "sp_secrets" {
  for_each = var.group_configs
  name         = "sp-secret-${replace(each.value.group_name, "_", "-")}"
  key_vault_id = data.azurerm_key_vault.vault.id
}

#
# Cluster Permissions
#
resource "databricks_permissions" "cluster_permissions" {
  for_each   = var.group_configs
  cluster_id = var.cluster_ids[each.key]

  access_control {
    group_name       = each.value.group_name
    permission_level = "CAN_RESTART"
  }

  access_control {
    service_principal_name = databricks_service_principal.group_sps[each.key].application_id
    permission_level       = "CAN_ATTACH_TO"
  }
}