
variable "enable_unified_catalog_isolation" {
  description = "If set to true, enables Unity Catalog Schemas per group, Shared SQL Warehouse, and Job creation permissions."
  type        = bool
  default     = false
}

variable "sql_warehouse_name" {
  description = "Name of the shared SQL Warehouse"
  type        = string
  default     = "Shared Student Warehouse"
}

variable "catalog_name" {
  description = "The Unity Catalog name where schemas will be created."
  type        = string
  default     = "94290_dev" # BUG: hard coded name
}
