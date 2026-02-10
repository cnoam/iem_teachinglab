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

## Destroying (clean teardown)
Terraform destroys the VM extension `AADSSHLoginForLinux`. Azure requires the VM
to be running to delete extensions; if the VM is deallocated, destroy can fail
with a 409 conflict. If that happens, skip the extension resources in state and
continue the destroy:

```bash
terraform workspace select dev

terraform state rm \
  'azurerm_virtual_machine_extension.entra_ssh["group_01"]' \
  'azurerm_virtual_machine_extension.entra_ssh["group_02"]'

terraform destroy -var "subscription_id=..."
```

After destroy, an orphaned OS disk can remain and block Resource Group deletion.
Check and delete any remaining disks:

```bash
az resource list -g course-group_01 -o table
az disk delete -g course-group_01 -n <OS_DISK_NAME> --yes
```

Then re-run `terraform destroy` or delete the RG:

```bash
az group delete -n course-group_01 --yes --no-wait
```

## Remote Backend and State Migration
This project is configured to use an Azure Storage backend. Update the backend block
in `versions.tf` with your course-specific values (The `key` so the state
file is unique per course).

### Migrate existing local state to the remote backend
1. Ensure the backend block in `versions.tf` is updated (course-specific `key`).
2. Reinitialize and migrate state:
   ```bash
   terraform init -migrate-state
   ```
3. Confirm the migration when prompted.
