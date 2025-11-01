output "users" {
  description = "Map of created users keyed by email address"
  value       = databricks_user.workspace_user
}