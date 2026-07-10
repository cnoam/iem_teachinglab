output "team_vm_names" {
  description = "VM resource names by team."
  value       = { for t, vm in azurerm_linux_virtual_machine.team : t => vm.name }
}

output "team_resource_groups" {
  description = "Resource group names by team."
  value       = { for t, rg in azurerm_resource_group.team : t => rg.name }
}

output "team_public_ip_addresses" {
  description = "Public IP addresses by team."
  value       = { for t, pip in azurerm_public_ip.team : t => pip.ip_address }
}

output "vm_fqdns" {
  description = "FQDNs by team when enable_fqdn = true (empty otherwise)."
  value       = { for t, pip in azurerm_public_ip.team : t => pip.fqdn }
}

output "auth_method" {
  description = "Auth method this course was deployed with."
  value       = var.auth_method
}

output "next_steps" {
  description = "Reminder of manual post-apply steps, printed at the end of `terraform apply`."
  value = local.is_entra ? (
    "auth_method=entra: no key deployment needed. Students run `az ssh vm ...`."
    ) : (
    "\n\n\nACTION REQUIRED while the VMs are up: run `ansible-playbook ../../ansible/playbooks/deploy-keys.yml` from this course folder to push each group's keys/<group>.pub into azureuser's authorized_keys.\nUse `../../scripts/vm-power.sh start|stop` to boot/deallocate all course VMs, or run the whole cycle (apply + start + ansible + stop) with `../../scripts/provision-course.sh`.\n\n\n"
  )
}
