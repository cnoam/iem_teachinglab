output "team_vm_names" {
  description = "VM resource names by team."
  value = {
    for team, _ in azurerm_linux_virtual_machine.team :
    team => azurerm_linux_virtual_machine.team[team].name
  }
}

output "team_resource_groups" {
  description = "Resource group names by team."
  value = {
    for team, _ in azurerm_resource_group.team :
    team => azurerm_resource_group.team[team].name
  }
}

output "team_public_ip_fqdns" {
  description = "Public IP FQDNs (may be null if you did not set DNS labels)."
  value = {
    for team, _ in azurerm_public_ip.team :
    team => azurerm_public_ip.team[team].fqdn
  }
}

output "team_public_ip_addresses" {
  description = "Public IP addresses by team."
  value = {
    for team, _ in azurerm_public_ip.team :
    team => azurerm_public_ip.team[team].ip_address
  }
}

output "subscription_id" {
  description = "Effective subscription ID (from var.subscription_id or current Azure CLI login)."
  value       = local.effective_subscription_id
}
