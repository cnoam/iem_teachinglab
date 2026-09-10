variable "user_names_file" {
  description = "Path to the CSV file containing usernames."
  type        = string
  default     = "./users.csv"
}

variable "databricks_profile" {
  description = "The Databricks CLI profile to use."
  type        = string
  default     = "default"
}

variable "workspace_profiles" {
  type        = map(string)
  description = "Maps TF workspace names to ~/.databrickscfg profile names"
}
