# Summary of Azure AD Application & Secret Automation Attempts

**Date:** February 9, 2026

This document summarizes the attempts to fully automate the creation of Azure AD Applications and their corresponding client secrets for Databricks Service Principals, and the reasons for reverting to a partially manual approach.

## Initial Goal
The primary objective was to entirely automate the provisioning of Databricks Service Principals (SPs) including:
1.  Creation of an Azure AD Application for each student group.
2.  Creation of an Azure AD Service Principal linked to each application.
3.  Automatic generation of a client secret for each application.
4.  Storing these secrets securely in Azure Key Vault.
5.  Linking these Azure AD SPs to Databricks Service Principals.

## Attempt 1: Full Terraform Automation (Original Approach)

**Method:**
*   Use `resource "azuread_application"` to create the application.
*   Set the `owners` property of the `azuread_application` to the `object_id` of the Terraform execution identity (the user running `terraform apply`). This was intended to grant permission to manage secrets.
*   Use `resource "azuread_application_password"` to generate the client secret.
*   Use `resource "azurerm_key_vault_secret"` to store the generated secret in Azure Key Vault.
*   Link to `databricks_service_principal` using the Azure AD Application's `client_id`.

**Outcome:** **Failed due to 403 (Forbidden) permissions error.**

**Reason for Failure:**
The Terraform execution identity (your `cnoam@technion.ac.il` user) lacked the necessary Azure AD permissions to *create* `azuread_application` resources. Specifically, roles like "Application Developer" or "Cloud Application Administrator" were missing.

## Attempt 2: Hybrid Automation - Admin Creates Applications, Terraform Manages Secrets

**Method:**
*   The proposal was for an Azure AD Administrator to *manualy* create the `azuread_application` objects.
*   The Administrator would also need to explicitly assign the Terraform execution identity as an **Owner** for each of these pre-created applications. This ownership is crucial, as an owner of an application can generate secrets for it, even without broader permissions to create *new* applications.
*   Terraform would then use `data "azuread_application"` to *read* the details of these pre-created applications.
*   `resource "azuread_application_password"` would then be used to generate and manage the secrets for these discovered applications.

**Outcome:** **Failed due to 403 (Forbidden) permissions error.**

**Reason for Failure:**
Even after ensuring the `az account get-access-token --resource-type ms-graph` command was used, repeated attempts to query the Microsoft Graph API for applications (`curl ... /v1.0/applications`) resulted in a 403. This indicated that the Terraform execution identity lacked even basic "Directory Readers" permissions in Azure AD to *read* existing application objects. Without the ability to read them, Terraform could not use `data "azuread_application"` to discover them.

## Current Solution (Manual Application Creation, Terraform Creates Secrets)

Given the stringent permission limitations, the most viable path is:

1.  **Azure AD Administrator Task (Manual):**
    *   Manually create each Azure AD Application for the student groups (e.g., `sp-group-01`, `sp-group-02`).
    *   **Crucially:** The Administrator must then manually assign the Terraform execution identity (e.g., `cnoam@technion.ac.il`'s object ID) as an **Owner** to *each* of these newly created applications.
    *   The Administrator must provide a mapping of each application's `client_id` (Application ID) and `object_id`.

2.  **Your Terraform Task (Automated Secret Generation):**
    *   The Terraform code is being adapted to accept these `client_id`s and `object_id`s as input variables.
    *   Terraform will then use `resource "azuread_application_password"` to generate a new client secret for the application (since the Terraform identity is an owner).
    *   This secret will be stored in Azure Key Vault (`resource "azurerm_key_vault_secret"`).
    *   Finally, the `databricks_service_principal` will be created/updated in Databricks, linking to the Azure AD Application using the provided `client_id`.

This approach ensures the critical secret generation and management can be automated by Terraform, even though the initial application object creation remains a manual step by an Azure AD Admin.

## Manual Method Used Previously

Prior to attempting the automation described above, the process for generating and managing Service Principal secrets involved the following manual steps:

1.  **Manual Secret Generation in Databricks UI:**
    *   For each Databricks Service Principal (which was created by Terraform as a placeholder), a Workspace Administrator would navigate to the Databricks UI (`Settings` -> `Service Principals`).
    *   For each `sp_XX` (e.g., `sp_01`), a new client secret would be manually generated.
    *   The generated secret value (which is shown only once) had to be copied immediately.

2.  **Temporary Storage:**
    *   The copied secrets were then typically stored temporarily in a local `secrets.csv` file. This file would contain entries mapping the group number to its corresponding secret value.

3.  **Key Vault Population via Script:**
    *   A custom utility script (`utils/populate_secrets_from_csv.sh`) was then executed. This script read the secrets from the `secrets.csv` file and uploaded them into the designated Azure Key Vault (`sp-secrets-94290`). This step acted as a bridge between the manual secret generation and Terraform's ability to read secrets from Key Vault.

4.  **Security Risk & Manual Overhead:**
    *   This method introduced significant manual overhead (copy-pasting 30+ secrets) and potential security risks due to secrets temporarily residing in a local file before being secured in Key Vault.
    *   It also relied on an Administrator's manual intervention every time secrets needed to be rotated or recreated.

