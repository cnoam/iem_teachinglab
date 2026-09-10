
terraform {
  required_providers {
    databricks = {
      source = "databricks/databricks"
    }
  }

  backend "local" {
    path = "dev.tfstate"
  }
}

provider "databricks" {
  profile = var.workspace_profiles[terraform.workspace]
}

data "local_file" "user_names" {
  filename = "./users.csv"
}

locals {
  groups      = csvdecode(data.local_file.user_names.content)
  group_count = length(local.groups)

  group_configs = {
    for i in range(local.group_count) : format("%02d", i + 1) => {
      index                  = i
      group_name             = format("group_%02d", i + 1)
      schema_name            = format("schema_%02d", i + 1)
      service_principal_name = format("sp_%02d", i + 1)
      cluster_name           = format("cluster_%02d", i + 1) # kept for output compatibility only
    }
  }

  group_members_flattened = flatten([
    for idx, group in local.groups : [
      for member in group : {
        group_name  = local.group_configs[format("%02d", idx + 1)].group_name
        member_name = trimspace(member)
      } if trimspace(member) != ""
    ]
  ])
}

data "databricks_current_config" "this" {}
output "dbr_workspace_id" {
  value = data.databricks_current_config.this.host
}
