# A KeyVault was used to store secrets for the Service Principal. This allows us to keep sensitive information out of our Terraform code and state files.
# kept here for reference, but not used in the final implementation as we switched to using Terraform Cloud's built-in secret management instead.

# variable "key_vault_name" {
#   description = "Name of the Azure Key Vault containing SP secrets"
#   type        = string
#   default     = "sp-secrets-94290"
# }

# variable "key_vault_rg" {
#   description = "Resource Group of the Key Vault"
#   type        = string
#   default     = "databricks-rg-2025"
# }

# data "azurerm_key_vault" "vault" {
#   name                = var.key_vault_name
#   resource_group_name = var.key_vault_rg
# }
