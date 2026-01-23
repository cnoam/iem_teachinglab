output "sql_warehouse_id" {
  description = "The ID of the shared SQL Warehouse (if enabled)"
  # Accessing via module output. Since SQL_ID is same for all, pick first group "01" (if exists) or handle map.
  # Better: The module outputs a map. I can just pick one value.
  value       = var.enable_unified_catalog_isolation && length(keys(module.uc_setup[0].sp_credentials_and_env_vars)) > 0 ? module.uc_setup[0].sp_credentials_and_env_vars["01"].DATABRICKS_SQL_ID : "Disabled"
  sensitive   = true
}

output "cluster_ids" {
  description = "Map of Group Name to Cluster ID"
  value       = { for k, v in databricks_cluster.clusters : k => v.id }
}

output "sp_credentials_and_env_vars" {
  value     = var.enable_unified_catalog_isolation ? module.uc_setup[0].sp_credentials_and_env_vars : null
  sensitive = true
}
