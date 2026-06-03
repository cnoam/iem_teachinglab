variable "location" {
  type        = string
  description = "Azure region (e.g. eastus)."
  default     = "eastus"
}

variable "subscription_id" {
  type        = string
  description = "Subscription where VMs are created."
  default     = "b3931bf1-b901-4dc2-bf3e-b020fa67cb8b"
}

variable "name_prefix" {
  type        = string
  description = "Prefix for resource naming (e.g. course code)."
  default     = "course"
}

variable "allowed_ssh_cidrs" {
  type        = list(string)
  description = "CIDRs allowed to access TCP/22 on the VMs."
  default     = ["0.0.0.0/0"]
}

variable "vm_size" {
  type        = string
  description = "VM size."
  default     = "Standard_D4as_v4"
}

variable "tags" {
  type        = map(string)
  description = "Tags applied to all Azure resources. Use to label test runs (e.g. environment=terraform-test)."
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
# gemini 2026-02-10 13:30
