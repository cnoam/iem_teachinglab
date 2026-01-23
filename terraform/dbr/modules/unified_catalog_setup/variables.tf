variable "group_configs" {
  description = "Map of group configurations derived from CSV"
  type = map(object({
    index                  = number
    group_name             = string
    schema_name            = string
    service_principal_name = string
    job_name               = string
    cluster_name           = string
  }))
}

variable "student_groups_csv_rows" {
  description = "Raw CSV rows (list of maps) for student groups"
  type        = list(map(string))
}

variable "group_members_flattened" {
  description = "Flattened list of all group members"
  type = list(object({
    group_name  = string
    member_name = string
  }))
}

variable "all_student_groups_name" {
  description = "Display name of the group containing all students"
  type        = string
}

variable "catalog_name" {
  description = "Unity Catalog name"
  type        = string
}

variable "sql_warehouse_name" {
  description = "Name of the shared SQL Warehouse"
  type        = string
}

variable "key_vault_name" {
  description = "Name of the Azure Key Vault"
  type        = string
}

variable "key_vault_rg" {
  description = "Resource Group of the Key Vault"
  type        = string
  default     = "databricks-rg-2025"
}

variable "databricks_host" {
  description = "Databricks host URL"
  type        = string
}

variable "cluster_ids" {
  description = "Map of cluster IDs keyed by group ID"
  type        = map(string)
}

variable "user_ids" {
  description = "List of user IDs to ensure dependency"
  type        = list(string)
  default     = []
}

variable "student_group_ids" {
  description = "List of student group IDs to ensure dependency"
  type        = list(string)
  default     = []
}