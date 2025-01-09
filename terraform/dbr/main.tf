
terraform {
  required_providers {
    databricks = {
      source = "databricks/databricks"
    }
  }
}

# FUTURE: use profiles
# # This will choose the needed profile from the terraform.tfvars file
# provider "databricks" {
#   # The host value is taken from the ~/.databrickscfg file
#   # it must not be present here too
#   # host = var.databricks_host
#   profile = "lab94290-integration-test" #var.databricks_profile
# }

provider "databricks" {
  # The host value is taken from the ~/.databrickscfg file
  # it must not be present here too
  host = var.databricks_host
  profile = var.databricks_profile  # The value used here MUST match one of the profile in ~/.databrickscfg
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


  group_members_flattened = flatten( [
    for idx, group in local.groups : [
      for member in group : {
        group_name = local.group_names[idx]
        member_name = trimspace(member)
      }if trimspace(member) != ""  # Filter out empty member names
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
