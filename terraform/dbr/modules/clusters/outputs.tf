output "clusters" {
  description = "Map of created clusters keyed by cluster name"
  value       = databricks_cluster.clusters
}