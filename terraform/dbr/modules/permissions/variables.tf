variable "student_groups" {
  description = "Map of student groups created by the groups module"
  type = map(object({
    id = string
  }))
}

variable "clusters" {
  description = "Map of clusters created by the clusters module"
  type = map(object({
    id = string
  }))
}

variable "permission_level" {
  description = "Permission level to assign to groups"
  type        = string
  default     = "CAN_RESTART"
}