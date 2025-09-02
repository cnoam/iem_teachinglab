
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
}

# Currently not needed, but kept here for educational purpose.
# The old coded needed it because I used "--target" . Now I don't, and all dependecies are
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
