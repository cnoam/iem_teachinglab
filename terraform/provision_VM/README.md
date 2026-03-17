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

## Ansible Management (Configuration & Labs)

This project uses Ansible for post-provisioning configuration. Terraform automatically generates `inventory.ini` and `ansible.cfg` in the root directory.

### 1. Initial Base Setup
Run this once after `terraform apply` to install Docker, configure NVMe disks, and prepare the base environment:
```bash
ansible-playbook playbooks/base_setup.yml
```

### 2. Deploying a Specific Lab
Run the lab-specific playbook (e.g., PostgreSQL vs. ClickHouse):
```bash
ansible-playbook playbooks/lab_pg_vs_ch.yml
```

### 3. Targeting Specific Teams
You can target a single team using the `-l` (limit) flag:
```bash
ansible-playbook -l group_01 playbooks/lab_pg_vs_ch.yml
```

## Testing

Deploys real VMs (~5 min total including teardown). RBAC assignments and the
VM extension are mocked so the test stays fast and doesn't require real Entra
users. Run locally or in CI:

```bash
terraform test
```

### Manual SSH / cloud-init verification

`terraform test` tears down resources immediately after assertions, so SSH
connectivity must be verified in a separate manual step:

```bash
terraform apply -var "subscription_id=..."   # deploy real VMs
bash tests/verify_ssh.sh                      # check cloud-init users on every VM
terraform destroy -var "subscription_id=..."  # clean up
```

`verify_ssh.sh` reads `terraform output team_public_ip_addresses`, SSHes into
each VM as `vmadmin`, and confirms that both `vmadmin` and `azureuser` exist.
It retries for up to 5 minutes to allow for VM boot time.

### Interrupting a test run

If you need to cancel `terraform test`, press `Ctrl+C` once and wait. Terraform
will attempt a graceful destroy before exiting. Expected wait times:

- teardown after `terraform test` — up to **15 min** if extension wasn't mocked; ~5 min with current mocks

If the graceful shutdown has been running for more than 15 minutes, press
`Ctrl+C` a second time to force-kill. Then check for and remove orphaned
resources manually (see below).

### Checking for dangling test resources

All resources created during tests carry the tag `environment=terraform-test`.
To find any that were not cleaned up:

```bash
az resource list --tag environment=terraform-test --output table
```

To delete all matching resource groups at once:

```bash
az group list --tag environment=terraform-test --query "[].name" -o tsv \
  | xargs -r -I {} az group delete -n {} --yes --no-wait
```

## References

- Microsoft Learn: "Sign in to a Linux virtual machine in Azure by using Microsoft Entra ID"
  https://learn.microsoft.com/en-us/entra/identity/devices/howto-vm-sign-in-azure-ad-linux


## NOTE on powering off
The automatic deallocation resource (`stop_vm`) is currently **commented out** in `main.tf` to allow for Ansible configuration.

**Manual deallocation is required to avoid compute costs.**

```bash
# Deallocate all team VMs (each lives in its own RG — use tags to find them all)
az resource list --tag project=iem-teachinglab \
  --query "[?type=='Microsoft.Compute/virtualMachines'].id" -o tsv \
  | xargs -r az vm deallocate --no-wait --ids

# Show only VMs that are NOT deallocated (i.e. running, starting, stopping, etc.)
az vm list --show-details \
  --query "[?tags.project=='iem-teachinglab' && powerState!='VM deallocated'].{name:name, state:powerState, rg:resourceGroup}" \
  -o table
```

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
