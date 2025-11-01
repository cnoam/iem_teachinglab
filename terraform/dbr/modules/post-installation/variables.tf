variable "clusters" {
  description = "Map of clusters created by the clusters module"
  type = map(object({
    id = string
  }))
}

variable "databricks_host" {
  description = "The URL of the Databricks workspace"
  type        = string
}

variable "databricks_token" {
  description = "The API token for Databricks authentication"
  type        = string
  sensitive   = true
}