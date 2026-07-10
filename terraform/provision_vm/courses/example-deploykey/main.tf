# Example course: SSH deploy keys (students submit a pubkey; deploy-keys.yml
# pushes it to azureuser). Web ports + FQDN enabled for Let's Encrypt labs.
module "vms" {
  source = "../../modules/team_vm"

  auth_method     = "deploy_key"
  users_csv_path  = "${path.root}/users.csv"
  subscription_id = var.subscription_id

  name_prefix = "example-deploykey" # MUST be unique across concurrent courses
  location    = "eastus"
  vm_size     = "Standard_B1s"

  open_web_ports = true
  enable_fqdn    = true
}

output "team_vm_names" { value = module.vms.team_vm_names }
output "team_resource_groups" { value = module.vms.team_resource_groups }
output "team_public_ip_addresses" { value = module.vms.team_public_ip_addresses }
output "vm_fqdns" { value = module.vms.vm_fqdns }
output "next_steps" { value = module.vms.next_steps }
