# SSH to Course VMs Using Technion SSO (Azure Entra ID)

Last updated: 2026-02-10

## What you need from the course staff
You will receive two values for your team VM:
- VM resource name (Example: `vm-team-01`, NOT the DNS name)
- Resource group (RG) (Example: `rg-team-01`)

## One-time setup on your computer
1. Install Azure CLI
   - Follow Microsoft’s official instructions for your OS: `https://learn.microsoft.com/cli/azure/install-azure-cli`
2. Install the Azure SSH extension (first time only)
   - `az extension add --name ssh`
3. Sign in using Technion SSO
   - `az login`

## Connect to your team VM
Run the command below with the VM name and RG you received.
- `az ssh vm -n <VM_RESOURCE_NAME> -g <RG>`

Example:
- `az ssh vm -n vm-team-01 -g rg-team-01`

## Common problems
- **AuthorizationFailed**
  - You are not assigned to this VM or RG. Contact course staff.
- **Resource not found**
  - You used a DNS/FQDN instead of the VM resource name, or you used the wrong RG.
- **Role was recently granted**
  - Log out and back in to refresh the token:
  - `az logout`
  - `az login`
- **Extension prompt**
  - If asked to install the ssh extension, type `Y` and let it install.
- **Received disconnect: Too many authentication failures** (troubleshooting)
  - Your SSH agent is offering too many keys. Retry with:
  - `az ssh vm -n <VM_RESOURCE_NAME> -g <RG> -- -o IdentitiesOnly=yes -o PubkeyAuthentication=yes -o PreferredAuthentications=publickey`
  - If it still fails, temporarily clear your agent: `ssh-add -D`, then try again.

## Notes
Use only `az ssh vm` for this course. Do not use plain `ssh user@host`. The course VMs are configured for Entra-based login via Azure CLI.
