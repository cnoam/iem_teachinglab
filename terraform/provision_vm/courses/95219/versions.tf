terraform {
  required_version = ">= 1.5.0"

  required_providers {
    azurerm = { source = "hashicorp/azurerm", version = ">= 3.100.0" }
    azuread = { source = "hashicorp/azuread", version = ">= 2.45.0" }
    tls     = { source = "hashicorp/tls", version = ">= 4.0.0" }
    local   = { source = "hashicorp/local", version = ">= 2.5.0" }
  }

  # Remote state (Azure Storage). The `key` MUST be unique per course — this is
  # what keeps concurrent courses isolated. Change it before first init.
  # For a throwaway local plan instead, comment this block out.
  backend "azurerm" {
    resource_group_name  = "ddsteachinglab-infrastructure-group"
    storage_account_name = "ddsteachinglabdatastg"
    container_name       = "terraform-states"
    key                  = "95219_deploykey.tfstate"
    subscription_id      = "5baf6ff6-d2b3-4df8-a9ca-3261f6424c01"
  }
}

provider "azurerm" {
  features {}
  subscription_id = var.subscription_id
}

provider "azuread" {}
