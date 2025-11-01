variable "users" {
  description = "List of user email addresses to create"
  type        = list(string)
}

variable "workspace_access" {
  description = "Whether to grant workspace access to users"
  type        = bool
  default     = false
}

variable "active" {
  description = "Whether the users should be active"
  type        = bool
  default     = true
}

output "users" {
  description = "Map of created users keyed by email address"
  value       = databricks_user.workspace_user
}