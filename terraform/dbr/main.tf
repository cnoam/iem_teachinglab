
terraform {
  required_providers {
    databricks = {
      source = "databricks/databricks"
    }
  }
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
