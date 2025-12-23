# After the cluster is created, it is in RUNNING state until the autotermination.
# Since we don't need it running now, turn it off using databricks CLI.

resource "null_resource" "terminate_clusters" {
  depends_on = [databricks_library.maven_library, databricks_library.python_library]
  for_each   = databricks_cluster.clusters

  # Add a local-exec provisioner to terminate the cluster immediately after creation
  provisioner "local-exec" {
    # We pull the profile name from the same map used in the provider
    command = <<EOT
      echo "Terminating cluster: ${each.key}"
      databricks clusters delete "${each.value.id}" --profile "${var.workspace_profiles[terraform.workspace]}"
    EOT
  }
}
