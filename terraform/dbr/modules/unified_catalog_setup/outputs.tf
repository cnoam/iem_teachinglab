output "sp_credentials_and_env_vars" {
  value = {
    for k, v in var.group_configs : k => {
      DATABRICKS_CLIENT_ID     = try(databricks_service_principal.group_sps[k].application_id, "")
      DATABRICKS_CLIENT_SECRET = try(data.azurerm_key_vault_secret.sp_secrets[k].value, "SECRET_NOT_FOUND_IN_KV")
      DATABRICKS_HOST          = var.databricks_host
      DATABRICKS_SQL_ID        = databricks_sql_endpoint.shared_warehouse.id
      DATABRICKS_CLUSTER_ID    = try(var.cluster_ids[k], "")
      DATABRICKS_CATALOG       = var.catalog_name
      DATABRICKS_SCHEMA        = v.schema_name
      DATABRICKS_SP_NAME       = v.service_principal_name
      DATABRICKS_GROUP_NAME    = v.group_name
      DATABRICKS_CLUSTER_NAME  = v.cluster_name
    }
  }
  sensitive = true
}
