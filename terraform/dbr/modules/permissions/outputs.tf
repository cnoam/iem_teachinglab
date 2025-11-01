output "cluster_permissions" {
  description = "Map of cluster permissions keyed by group name"
  value       = databricks_permissions.cluster_permissions
}