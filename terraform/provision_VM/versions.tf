terraform {
  required_version = ">= 1.5.0"

  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = ">= 3.100.0"
    }
    azuread = {
      source  = "hashicorp/azuread"
      version = ">= 2.45.0"
    }
    tls = {
      source  = "hashicorp/tls"
      version = ">= 4.0.0"
    }
  }

  # Remote state backend (Azure Storage). Update the key per course.
  backend "azurerm" {
    resource_group_name  = "ddsteachinglab-infrastructure-group"
    storage_account_name = "ddsteachinglabdatastg"
    container_name       = "terraform-states"
    key                  = "course-<COURSE_ID>.tfstate"
    subscription_id      = "5baf6ff6-d2b3-4df8-a9ca-3261f6424c01"
  }
}

provider "azurerm" {
  features {}
  subscription_id = local.effective_subscription_id
}

provider "azuread" {}
