
# Jobs
#
# Creates a Databricks Job for each student group.
# The job is configured to run a sample notebook.
# These jobs are samples for the users (students).
#

resource "databricks_job" "group_jobs" {
  for_each = var.enable_unified_catalog_isolation ? local.group_configs : {}

  name = each.value.job_name


  # optional. If not used, DBR will use serverless
  /*
   job_cluster {
     job_cluster_key = "${each.value.job_name}_cluster"
     new_cluster {
       spark_version   = var.spark_version
       node_type_id    = "Standard_DS3_v2" # Example node type
       driver_node_type_id = "Standard_DS3_v2" # Example driver node type
       num_workers     = 1
     }
   }
*/

  # run_as {
  # service_principal_name = databricks_service_principal.group_sps[each.key].application_id
  #   }

  task {
    task_key = "run_notebook"
    #job_cluster_key = "${each.value.job_name}_cluster"
    notebook_task {
      notebook_path = "/Shared/sample_notebook"
      base_parameters = {
        "group_name" = each.value.group_name # Using the student DB group name
        catalog      = var.catalog_name
        schema       = databricks_schema.group_schemas[each.key].name
      }
    }
  }
}

#
# Grants for Job Permissions
#
# Grants the Service Principal for each group 'Can Manage Run' on their respective job.
#

resource "databricks_permissions" "sp_job_permissions" {
  for_each = var.enable_unified_catalog_isolation ? local.group_configs : {}

  job_id = databricks_job.group_jobs[each.key].id

  access_control {
    service_principal_name = databricks_service_principal.group_sps[each.key].application_id
    permission_level       = "CAN_MANAGE_RUN"
  }
}