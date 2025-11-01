# Post-Installation Module

This module handles post-installation tasks, such as terminating clusters after library installation.

## Variables

- `clusters` - Map of clusters created by the clusters module
- `databricks_host` - The URL of the Databricks workspace
- `databricks_token` - The API token for Databricks authentication

## Resources

- `null_resource.terminate_clusters` - Terminates clusters using the Databricks API