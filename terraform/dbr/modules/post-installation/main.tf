# After the cluster is created, it is in RUNNING state until the autotermination.
# Since we don't need it running now, turn it off using REST API.

resource "null_resource" "terminate_clusters" {
  for_each = var.clusters

  # Add a local-exec provisioner to terminate the cluster immediately after creation
  provisioner "local-exec" {
    command = <<EOT
      echo "Terminating cluster: ${each.key}"
      curl -X POST https://${var.databricks_host}/api/2.0/clusters/delete \
      -H "Authorization: Bearer ${var.databricks_token}" \
      -d '{"cluster_id": "${each.value.id}"}'
    EOT
  }
}