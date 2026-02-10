# Team VMs with Microsoft Entra (Azure AD) SSH Login

This Terraform creates:
- One Resource Group per team
- Ubuntu VM + NIC + Public IP + NSG allowing SSH (TCP/22)
- Installs the `AADSSHLoginForLinux` extension (Entra SSH login)
- Assigns RBAC for each team member:
  - Reader on the team RG (required for `az ssh vm`)
  - Virtual Machine User Login on the VM (authorizes Entra SSH)

## Inputs

- users.csv file , containing one group per row
- The Terraform identity must be able to resolve Entra users via `data.azuread_user`
  (directory read permissions).

## Running `apply`
you must supply the subscription ID, either as command line or in tfvars.

example:<br>
tf apply -var `"subscription_id=b3931bf1-b901-4dc2-bf3e-b020fa67cb8b" -parallelism=60`

## Student connection command

Students use:

```bash
az login
az ssh vm -n <VM_RESOURCE_NAME> -g <RG>
```

VM and RG values can be taken from the outputs, or shared per team.

## References

- Microsoft Learn: "Sign in to a Linux virtual machine in Azure by using Microsoft Entra ID"
  https://learn.microsoft.com/en-us/entra/identity/devices/howto-vm-sign-in-azure-ad-linux


## NOTE on powering off
At the end of the provisioning, the VMs are stopped(deallocated).

**But there is no mechanism to power off after idle time.**

## Remote Backend and State Migration
This project is configured to use an Azure Storage backend. Update the backend block
in `versions.tf` with your course-specific values (especially the `key` so the state
file is unique per course).

### Migrate existing local state to the remote backend
1. Ensure the backend block in `versions.tf` is updated (course-specific `key`).
2. Reinitialize and migrate state:
   ```bash
   terraform init -migrate-state
   ```
3. Confirm the migration when prompted.
