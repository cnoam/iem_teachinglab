variable "group_names" {
  description = "List of group names used to create corresponding clusters"
  type        = list(string)
}

variable "spark_version" {
  description = "Spark version"
  type        = string
  default     = "15.4.x-cpu-ml-scala2.12"
}

variable "min_workers" {
  description = "Minimal Worker node count"
  type        = number
  default     = 1
}

variable "max_workers" {
  description = "Max Worker node count"
  type        = number
  default     = 6
}

variable "autotermination_minutes" {
  description = "Auto termination [minutes]"
  type        = number
  default     = 20
}

variable "node_type_id" {
  description = "Node type ID for worker nodes"
  type        = string
  default     = "Standard_DS3_v2"
}

variable "driver_node_type_id" {
  description = "Node type ID for driver node"
  type        = string
  default     = "Standard_DS3_v2"
}

variable "custom_tags" {
  description = "Custom tags to apply to clusters"
  type        = map(string)
  default     = { "origin" = "terraform" }
}

variable "cluster_log_destination" {
  description = "Destination for cluster logs"
  type        = string
  default     = "dbfs:/cluster-logs"
}

variable "pyspark_python" {
  description = "Python interpreter for PySpark"
  type        = string
  default     = "/databricks/python3/bin/python3"
}

variable "enable_elastic_disk" {
  description = "Enable elastic disk for clusters"
  type        = bool
  default     = true
}

variable "data_security_mode" {
  description = "Data security mode for clusters"
  type        = string
  default     = "NONE"
}

variable "runtime_engine" {
  description = "Runtime engine for clusters"
  type        = string
  default     = "STANDARD"
}

variable "is_pinned" {
  description = "Pin clusters to prevent automatic termination"
  type        = bool
  default     = true
}