# Example course: Microsoft Entra SSH login (students connect with `az ssh vm`).
module "vms" {
  source = "../../modules/team_vm"

  auth_method     = "entra"
  users_csv_path  = "${path.root}/users.csv"
  subscription_id = var.subscription_id

  name_prefix = "example-entra" # MUST be unique across concurrent courses
  location    = "eastus"
  vm_size     = "Standard_D4as_v4"

  allowed_ssh_cidrs = ["0.0.0.0/0"]
}

output "team_vm_names" { value = module.vms.team_vm_names }
output "team_resource_groups" { value = module.vms.team_resource_groups }
output "team_public_ip_addresses" { value = module.vms.team_public_ip_addresses }
output "next_steps" { value = module.vms.next_steps }
