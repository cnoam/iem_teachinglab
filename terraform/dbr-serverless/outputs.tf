output "sql_warehouse_id" {
  description = "The ID of the shared SQL Warehouse"
  value       = var.enable_unified_catalog_isolation && length(keys(module.uc_setup[0].sp_credentials_and_env_vars)) > 0 ? module.uc_setup[0].sp_credentials_and_env_vars["01"].DATABRICKS_SQL_ID : "Disabled"
  sensitive   = true
}

output "sp_credentials_and_env_vars" {
  value     = var.enable_unified_catalog_isolation ? module.uc_setup[0].sp_credentials_and_env_vars : null
  sensitive = true
}
