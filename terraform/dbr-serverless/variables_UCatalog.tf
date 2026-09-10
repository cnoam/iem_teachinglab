# Serverless compute requires Unity Catalog; this flag defaults to true here.
variable "enable_unified_catalog_isolation" {
  description = "Enables UC schemas, SQL Warehouse, and SP secrets per group. Should stay true for serverless."
  type        = bool
  default     = true
}

variable "sql_warehouse_name" {
  description = "Name of the shared SQL Warehouse"
  type        = string
  default     = "Shared Student Warehouse"
}

variable "catalog_name" {
  description = "The Unity Catalog name where schemas will be created."
  type        = string
  default     = "94290_dev" # override in .tfvars per course
}

variable "course_data_storage_account" {
  description = "Azure storage account (ADLS Gen2) holding the shared, read-only course dataset containers."
  type        = string
}

variable "course_data_containers" {
  description = "Blob containers on course_data_storage_account to expose read-only, one external volume per container. Set, not list, so for_each keys are stable."
  type        = set(string)
}

variable "course_data_access_connector_id" {
  description = "Azure resource ID of the Databricks Access Connector whose managed identity has Storage Blob Data Reader + Storage Blob Delegator on course_data_storage_account (see docs/course_data_storage_setup.md). Reused here rather than creating a new connector."
  type        = string
}
