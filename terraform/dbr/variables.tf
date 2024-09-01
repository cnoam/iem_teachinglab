# variables.tf

# Databricks host URL
variable "databricks_host" {
  description = "The URL of the Databricks workspace."
  type        = string
}

# Databricks API token
variable "databricks_token" {
  description = "The API token for Databricks authentication."
  type        = string
  sensitive   = true
}

# Usernames CSV file
variable "user_names_file" {
  description = "Path to the CSV file containing usernames."
  type        = string
  default     = "./users.csv"
}

variable "spark_version" {
  description = "Spark version"
  type        = string
  default     = "14.3.x-scala2.12"
}

variable "min_workers" {
  description = "minimal Worker node count"
  type        = number
  default     = 1
}

variable "max_workers" {
  description = "max Worker node count"
  type        = number
  default     = 6
}

variable "autotermination_minutes" {
  description = "Auto termination [minutes]"
  type        = number
  default     = 15
}