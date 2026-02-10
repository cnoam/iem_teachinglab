variable "location" {
  type        = string
  description = "Azure region (e.g. eastus)."
  default     = "eastus"
}

variable "subscription_id" {
  type        = string
  description = "Subscription where VMs are created."
  default     = null
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
  default     = "Standard_B2s"
}

variable "ubuntu_sku" {
  type        = string
  description = "Ubuntu SKU (e.g. 22_04-lts)."
  default     = "22_04-lts"
}
# gemini 2026-02-10 13:30
