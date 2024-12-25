# variables.tf

# If using the  ~/.databrickscfg file, do NOT define the vars here
# since TF will require it defined explicitly
#
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
  default     = 20
}
# FUTURE: use profiles.
# variable "databricks_profile" {
#   description = "The Databricks CLI profile to use."
#   type        = string
#   default     = "lab94290-integration-test" # Replace with a sensible default if needed
# }


#
# variable "maven_packages" {
#   type    = list(string)
#   default = ["com.johnsnowlabs.nlp:spark-nlp_2.12:4.4.2"]
# }
#
# variable "python_packages" {
#   type    = list(string)
#   default = ["com.johnsnowlabs.nlp:spark-nlp_2.12:4.4.2"]
# }