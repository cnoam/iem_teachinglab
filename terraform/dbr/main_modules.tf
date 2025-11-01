terraform {
  required_providers {
    databricks = {
      source = "databricks/databricks"
    }
  }

  # This resource describe WHERE we keep the state file.
  # It does not change when deploying to other subscriptipions.
  backend "azurerm" {
    resource_group_name  = "ddsteachinglab-infrastructure-group"
    storage_account_name = "ddsteachinglabdatastg"
    container_name       = "terraform-states"
    key                  = "terraform.tfstate"
    subscription_id      = "5baf6ff6-d2b3-4df8-a9ca-3261f6424c01"
  }

# If using local state, put the above clause in comment, and uncomment the one below. See the Readme.md
#  backend "local" {
#    path = "dev.tfstate"   # re-use the file you just pulled
#  }
}

# This is the subscription where operations will be executed.
provider "azurerm" {
  # The subscription_id is read directly from the azure auth.
  # so you need to first "az login"
  # subscription_id = "dfabd25-794a-4610-a071-2dc334da70b7" # second subscription
  features {}
}

provider "databricks" {
  host    = "https://${var.databricks_host}"
  token   = var.databricks_token # workspace PA Token
}

# Read the CSV file using data source
data "local_file" "user_names" {
  #filename = var.user_names_file   # get the file name from user
  filename = "./users.csv"
}

# Decode the CSV content
locals {
  # Parse the CSV into a list of maps, where each map is a group of students
  groups = csvdecode(data.local_file.user_names.content)

  # Generate group names like "group_01", "group_02", etc.
  group_names = [for i in range(length(local.groups)) : format("group_%02d", i + 1)]

  group_members_flattened = flatten([
    for idx, group in local.groups : [
      for member in group : {
        group_name  = local.group_names[idx]
        member_name = trimspace(member)
      } if trimspace(member) != "" # Filter out empty member names
    ]
  ])
  
  # Extract unique user emails
  user_emails = [for m in local.group_members_flattened : m.member_name]
}

# Module for creating users
module "users" {
  source = "./modules/users"

  users            = local.user_emails
  workspace_access = false
  active           = true
}

# Module for creating groups
module "groups" {
  source = "./modules/groups"

  group_names              = local.group_names
  users                    = module.users.users
  group_members            = local.group_members_flattened
  all_student_groups_name  = "all_student_groups"
  databricks_sql_access    = true
  workspace_access         = true
}

# Module for creating clusters
module "clusters" {
  source = "./modules/clusters"

  group_names              = local.group_names
  spark_version            = var.spark_version
  min_workers              = var.min_workers
  max_workers              = var.max_workers
  autotermination_minutes  = var.autotermination_minutes
}

# Module for setting permissions
module "permissions" {
  source = "./modules/permissions"

  student_groups   = module.groups.student_groups
  clusters         = module.clusters.clusters
  permission_level = "CAN_RESTART"
}

# Module for installing libraries
module "libraries" {
  source = "./modules/libraries"

  clusters        = module.clusters.clusters
  maven_packages  = var.maven_packages
  python_packages = var.python_packages
}

# Module for post-installation tasks (terminating clusters)
module "post_installation" {
  source = "./modules/post-installation"

  clusters         = module.clusters.clusters
  databricks_host  = var.databricks_host
  databricks_token = var.databricks_token

  depends_on = [module.libraries]
}