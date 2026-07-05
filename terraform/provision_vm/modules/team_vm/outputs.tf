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
