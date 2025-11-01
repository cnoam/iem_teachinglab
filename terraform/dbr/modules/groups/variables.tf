variable "group_names" {
  description = "List of group names to create"
  type        = list(string)
}

variable "all_student_groups_name" {
  description = "Name for the group that contains all student groups"
  type        = string
  default     = "all_student_groups"
}

variable "databricks_sql_access" {
  description = "Whether to grant Databricks SQL access to the all students group"
  type        = bool
  default     = true
}

variable "workspace_access" {
  description = "Whether to grant workspace access to the all students group"
  type        = bool
  default     = true
}

variable "users" {
  description = "Map of users created by the users module"
  type        = map(object({
    id = string
  }))
}

variable "group_members" {
  description = "List of objects containing group_name and member_name mappings"
  type = list(object({
    group_name  = string
    member_name = string
  }))
}