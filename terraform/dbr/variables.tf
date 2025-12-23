# variables.tf

# Usernames CSV file
variable "user_names_file" {
  description = "Path to the CSV file containing usernames."
  type        = string
  default     = "./users.csv"
}

variable "spark_version" {
  description = "Spark version"
  type        = string
  # see https://learn.microsoft.com/en-us/azure/databricks/release-notes/runtime/
  default = "15.4.x-cpu-ml-scala2.12"
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


variable "databricks_profile" {
  description = "The Databricks CLI profile to use."
  type        = string
  default     = "default"
}



variable "maven_packages" {
  type = map(object({
    coordinates = string
    repo        = string
  }))
  default = {
    "spark_nlp" = {
      coordinates = "com.johnsnowlabs.nlp:spark-nlp_2.12:5.5.2"
      repo        = "https://maven.johnsnowlabs.com"
    }
  }
}

variable "python_packages" {
  type    = list(string)
  default = [ ]
}

variable "workspace_profiles" {
  type = map(string)
  description = "Maps TF workspace names to ~/.databrickscfg profile names"
  # Example: { "dev" = "dbr-dev", "prod" = "dbr-prod" }
}
