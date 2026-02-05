
terraform {
  required_providers {
    databricks = {
      source = "databricks/databricks"
    }
  }

  # This resource describe WHERE we keep the state file.
  # It does not change when deploying to other subscriptions.
  backend "azurerm" {
    resource_group_name  = "ddsteachinglab-infrastructure-group"
    storage_account_name = "ddsteachinglabdatastg"
    container_name       = "terraform-states"
    key                  = "terraform.tfstate"
    subscription_id      = "5baf6ff6-d2b3-4df8-a9ca-3261f6424c01"
  }

  # If using local state, put the above clause in comment, and uncomment the one below. See the Readme.md
  # backend "local" {
  #   path = "dev.tfstate" # re-use the file you just pulled
  # }
}

# This is the subscription where operations will be executed.
provider "azurerm" {
  features {}
  # BUG hardecoded value
  subscription_id = "b3931bf1-b901-4dc2-bf3e-b020fa67cb8b"
  #resource_provider_registrations = "none"
}

provider "databricks" {
  # Terraform looks up the host and token inside the ~/.databrickscfg
  # based on the profile name selected here.
  profile = var.workspace_profiles[terraform.workspace]
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

  # Number of groups, derived from the CSV file
  group_count = length(local.groups)

  # Create a map where keys are "01", "02", etc., and values are objects
  # containing all names for that logical group.
  group_configs = {
    for i in range(local.group_count) : format("%02d", i + 1) => {
      index                  = i
      group_name             = format("group_%02d", i + 1)
      schema_name            = format("schema_%02d", i + 1)
      service_principal_name = format("sp_%02d", i + 1)
      #job_name               = format("job_%02d", i + 1)
      cluster_name = format("cluster_%02d", i + 1)
    }
  }

  # Flattened list of student members and their assigned group names (from CSV)
  group_members_flattened = flatten([
    for idx, group in local.groups : [
      for member in group : {
        group_name  = local.group_configs[format("%02d", idx + 1)].group_name # Updated reference
        member_name = trimspace(member)
      } if trimspace(member) != "" # Filter out empty member names
    ]
  ])
}

# Currently not needed, but kept here for educational purpose.
# The old coded needed it because I used "--target" . Now I don't, and all dependencies are
# correctly placed.

# # Add a null resource that depends on the cluster/group creation
# # This will allow me to use `terraform apply --target null_resource.force_creation"
# # without the "install_libs" which depends (implicitly) on the cluster IDs
# #
# # To find which resource need to be in the list, I created dependency graph
# # by `tf graph > graph.dot && dot -Tpng graph.dot -o graph.png`
# resource "null_resource" "force_creation" {
#   depends_on = [
#     databricks_permissions.cluster_permissions,
#     databricks_group_member.student_assignments,
#     databricks_group_member.all_students_group_assignment
#   ]
# }



data "databricks_current_config" "this" {}
output "dbr_workspace_id" {
  value = data.databricks_current_config.this.host
}