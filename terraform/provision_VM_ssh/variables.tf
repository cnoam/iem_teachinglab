variable "location" {
  type        = string
  description = "Azure region (e.g. eastus)."
  default     = "eastus"
}

variable "subscription_id" {
  type        = string
  description = "Subscription where VMs are created. Must be set explicitly — no default to prevent accidental cross-subscription deploys."
}

variable "name_prefix" {
  type        = string
  description = "Prefix for resource naming (e.g. course code)."
  default     = "course"
}

variable "vm_size" {
  type        = string
  description = "VM size."
  default     = "Standard_B1s"
}

variable "tags" {
  type        = map(string)
  description = "Tags applied to all Azure resources."
  default = {
    project    = "iem-teachinglab"
    managed_by = "terraform"
  }
}

variable "auto_shutdown_time" {
  type        = string
  description = "Daily auto-shutdown time in HHMM format (24h, UTC). Set to empty string to disable."
  default     = "2350"
}
