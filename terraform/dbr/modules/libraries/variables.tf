variable "clusters" {
  description = "Map of clusters created by the clusters module"
  type = map(object({
    id = string
  }))
}

variable "maven_packages" {
  type = map(object({
    coordinates = string
    repo        = string
  }))
  default = {}
}

variable "python_packages" {
  type    = list(string)
  default = []
}