output "sql_warehouse_id" {
  description = "The ID of the shared SQL Warehouse (if enabled)"
  value       = var.enable_unified_catalog_isolation ? databricks_sql_endpoint.shared_warehouse[0].id : "Disabled"
}

output "cluster_ids" {
  description = "Map of Group Name to Cluster ID"
  value       = { for k, v in databricks_cluster.clusters : k => v.id }
}
