variable "auth_method" {
  type        = string
  description = "How students authenticate to their VM: 'entra' (az ssh vm via Microsoft Entra) or 'deploy_key' (SSH key pushed by Ansible to azureuser)."

  validation {
    condition     = contains(["entra", "deploy_key"], var.auth_method)
    error_message = "auth_method must be 'entra' or 'deploy_key'."
  }
}

variable "users_csv_path" {
  type        = string
  description = "Path to the course roster CSV (one row per group, columns = member emails). Pass path.root/users.csv from the course root."
}

variable "subscription_id" {
  type        = string
  description = "Subscription where VMs are created. No default — set explicitly per course to prevent cross-subscription deploys."
}

variable "name_prefix" {
  type        = string
  description = "Prefix for all resource names. MUST be unique per concurrent course — the self-deallocate custom role is subscription-scoped and keyed by this prefix."
}

variable "location" {
  type        = string
  description = "Azure region."
  default     = "eastus"
}

variable "vm_size" {
  type        = string
  description = "VM size."
  default     = "Standard_B1s"
}

variable "auto_shutdown_time" {
  type        = string
  description = "Daily auto-shutdown time, HHMM (24h, UTC). Empty string disables the daily schedule (the in-guest idle-watcher still runs)."
  default     = "2350"
}

variable "allowed_ssh_cidrs" {
  type        = list(string)
  description = "Source CIDRs allowed to reach TCP/22. Default open to the world (key-only auth)."
  default     = ["0.0.0.0/0"]
}

variable "open_web_ports" {
  type        = bool
  description = "Open TCP/80 and TCP/443 (e.g. for Let's Encrypt + student web apps)."
  default     = false
}

variable "enable_fqdn" {
  type        = bool
  description = "Assign a DNS label to each public IP, giving <name_prefix>-<group>.<region>.cloudapp.azure.com. Required for Let's Encrypt."
  default     = false
}

variable "idle_shutdown_hours" {
  type        = number
  description = "Hours of low CPU load before the in-guest idle-watcher deallocates the VM."
  default     = 4
}

variable "tags" {
  type        = map(string)
  description = "Tags applied to all Azure resources. Add environment=terraform-test to label throwaway runs."
  default = {
    project    = "iem-teachinglab"
    managed_by = "terraform"
  }
}
