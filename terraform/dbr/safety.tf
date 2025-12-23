# This resource exists solely to validate your environment before any action is taken
resource "terraform_data" "workspace_validation" {
  lifecycle {
    precondition {
      # Checks if the current workspace exists as a key in your profile map
      condition     = contains(keys(var.workspace_profiles), terraform.workspace)
      
      error_message = <<EOT
CRITICAL ERROR: Workspace Mismatch
The active Terraform workspace is '${terraform.workspace}', but this workspace is not defined in your 'workspace_profiles' variable.

To fix this:
1. Run 'terraform workspace list' to see available environments.
2. Run 'terraform workspace select <name>' to switch to a valid environment.
3. Or, add '${terraform.workspace}' to your 'workspace_profiles' map in your .tfvars file.
EOT
    }
  }
}