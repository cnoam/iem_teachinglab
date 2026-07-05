# One Azure VM per student group, driven by a course roster CSV.
#
# Common to both auth methods: network, VM, daily + idle auto-shutdown,
# Reader + VM Contributor RBAC, a self-deallocate managed-identity role.
# Auth-specific (gated on var.auth_method): the Entra SSH-login extension and
# the Virtual Machine User Login role assignment. The deploy_key method needs
# nothing extra in Terraform — keys are pushed post-apply by deploy-keys.yml.

data "local_file" "user_names" {
  filename = var.users_csv_path
}

locals {
  groups      = csvdecode(data.local_file.user_names.content)
  group_count = length(local.groups)

  group_configs = {
    for i in range(local.group_count) : format("%02d", i + 1) => {
      group_name = format("group_%02d", i + 1)
    }
  }

  group_members_flattened = flatten([
    for idx, group in local.groups : [
      for member in group : {
        group               = local.group_configs[format("%02d", idx + 1)].group_name
        user_principal_name = trimspace(member)
      } if trimspace(member) != ""
    ]
  ])

  teams = distinct([for gm in local.group_members_flattened : gm.group])

  team_members = {
    for t in local.teams :
    t => distinct([for gm in local.group_members_flattened : gm.user_principal_name if gm.group == t])
  }

  # One VM per team, keyed by team name. each.key == team throughout.
  team_vms = { for t in local.teams : t => { team = t } }

  # (team, upn) pairs for RBAC. vm_key == team since there is one VM per team.
  team_member_pairs = flatten([
    for t, members in local.team_members : [
      for upn in members : { team = t, upn = upn }
    ]
  ])

  is_entra = var.auth_method == "entra"
}

# Resolve Entra users (UPN -> objectId) for RBAC. Needs directory read on the
# Terraform identity. Required for both auth methods (Reader + VM Contributor).
data "azuread_user" "members" {
  for_each            = toset(distinct([for gm in local.group_members_flattened : gm.user_principal_name]))
  user_principal_name = each.value
}

# --- Bootstrap admin keypair (vmadmin). Written into the course root so the
#     generated inventory/ansible.cfg can find id_rsa_lab.pem next to them. ---
resource "tls_private_key" "bootstrap" {
  algorithm = "RSA"
  rsa_bits  = 4096
}

resource "local_file" "private_key" {
  filename        = "${path.root}/id_rsa_lab.pem"
  content         = tls_private_key.bootstrap.private_key_openssh
  file_permission = "0600"
}

resource "local_file" "public_key" {
  filename = "${path.root}/id_rsa_lab.pub"
  content  = tls_private_key.bootstrap.public_key_openssh
}

# --- Network + VM, one per team ---

resource "azurerm_resource_group" "team" {
  for_each = local.team_members

  name     = "${var.name_prefix}-${each.key}"
  location = var.location
  tags     = var.tags
}

resource "azurerm_virtual_network" "team" {
  for_each = local.team_members

  name                = "${var.name_prefix}-${each.key}-vnet"
  location            = azurerm_resource_group.team[each.key].location
  resource_group_name = azurerm_resource_group.team[each.key].name
  address_space       = ["10.${100 + index(local.teams, each.key)}.0.0/16"]
  tags                = var.tags
}

resource "azurerm_subnet" "team" {
  for_each = local.team_members

  name                 = "subnet-1"
  resource_group_name  = azurerm_resource_group.team[each.key].name
  virtual_network_name = azurerm_virtual_network.team[each.key].name
  address_prefixes     = ["10.${100 + index(local.teams, each.key)}.1.0/24"]
}

resource "azurerm_network_security_group" "team" {
  for_each = local.team_members

  name                = "${var.name_prefix}-${each.key}-nsg"
  location            = azurerm_resource_group.team[each.key].location
  resource_group_name = azurerm_resource_group.team[each.key].name
  tags                = var.tags

  security_rule {
    name                       = "allow-ssh"
    priority                   = 100
    direction                  = "Inbound"
    access                     = "Allow"
    protocol                   = "Tcp"
    source_port_range          = "*"
    destination_port_range     = "22"
    source_address_prefixes    = var.allowed_ssh_cidrs
    destination_address_prefix = "*"
  }

  # 80 (Let's Encrypt HTTP-01 + redirect) and 443, only when requested.
  dynamic "security_rule" {
    for_each = var.open_web_ports ? { "allow-http" = { port = "80", prio = 105 }, "allow-https" = { port = "443", prio = 110 } } : {}
    content {
      name                       = security_rule.key
      priority                   = security_rule.value.prio
      direction                  = "Inbound"
      access                     = "Allow"
      protocol                   = "Tcp"
      source_port_range          = "*"
      destination_port_range     = security_rule.value.port
      source_address_prefix      = "Internet"
      destination_address_prefix = "*"
    }
  }
}

resource "azurerm_public_ip" "team" {
  for_each = local.team_vms

  name                = "${var.name_prefix}-${each.key}-pip"
  location            = azurerm_resource_group.team[each.key].location
  resource_group_name = azurerm_resource_group.team[each.key].name
  allocation_method   = "Static"
  sku                 = "Standard"
  # FQDN: <name_prefix>-<group>.<region>.cloudapp.azure.com (Let's Encrypt needs a name, not a bare IP).
  domain_name_label = var.enable_fqdn ? "${var.name_prefix}-${replace(each.key, "_", "-")}" : null
  tags              = var.tags
}

resource "azurerm_network_interface" "team" {
  for_each = local.team_vms

  name                = "${var.name_prefix}-${each.key}-nic"
  location            = azurerm_resource_group.team[each.key].location
  resource_group_name = azurerm_resource_group.team[each.key].name
  tags                = var.tags

  ip_configuration {
    name                          = "ipconfig1"
    subnet_id                     = azurerm_subnet.team[each.key].id
    private_ip_address_allocation = "Dynamic"
    public_ip_address_id          = azurerm_public_ip.team[each.key].id
  }
}

resource "azurerm_network_interface_security_group_association" "team" {
  for_each = local.team_vms

  network_interface_id      = azurerm_network_interface.team[each.key].id
  network_security_group_id = azurerm_network_security_group.team[each.key].id
}

resource "azurerm_linux_virtual_machine" "team" {
  for_each = local.team_vms

  name                = "${var.name_prefix}-${each.key}"
  computer_name       = "${var.name_prefix}-${replace(each.key, "_", "-")}"
  resource_group_name = azurerm_resource_group.team[each.key].name
  location            = azurerm_resource_group.team[each.key].location
  size                = var.vm_size

  admin_username                  = "vmadmin"
  disable_password_authentication = true

  network_interface_ids = [azurerm_network_interface.team[each.key].id]

  admin_ssh_key {
    username   = "vmadmin"
    public_key = tls_private_key.bootstrap.public_key_openssh
  }

  # cloud-init: keep vmadmin's injected key, create keyless azureuser (the
  # student account), install Docker + Azure CLI, harden SSH, arm the
  # idle-watcher. Identical for both auth methods.
  custom_data = base64encode(templatefile("${path.module}/cloud-init.yaml", {
    idle_shutdown_hours = var.idle_shutdown_hours
  }))

  tags = var.tags

  os_disk {
    caching              = "ReadWrite"
    storage_account_type = "Standard_LRS"
  }

  source_image_reference {
    publisher = "Canonical"
    offer     = "ubuntu-24_04-lts"
    sku       = "server"
    version   = "latest"
  }

  # Used by the in-guest idle-watcher for `az login --identity` to self-deallocate.
  identity {
    type = "SystemAssigned"
  }
}

# --- Cost control ---

resource "azurerm_dev_test_global_vm_shutdown_schedule" "team" {
  for_each = var.auto_shutdown_time != "" ? local.team_vms : {}

  virtual_machine_id    = azurerm_linux_virtual_machine.team[each.key].id
  location              = azurerm_resource_group.team[each.key].location
  enabled               = true
  daily_recurrence_time = var.auto_shutdown_time
  timezone              = "UTC"

  notification_settings {
    enabled         = true
    email           = local.team_members[each.key][0]
    time_in_minutes = 30
  }

  tags = var.tags
}

# Each VM's managed identity may deallocate/read ONLY itself — powers the
# in-guest idle-watcher. 'start' is deliberately omitted. Common to both methods.
resource "azurerm_role_definition" "self_deallocate" {
  name        = "vm-self-deallocate-${var.name_prefix}"
  scope       = "/subscriptions/${var.subscription_id}"
  description = "Allow a VM's managed identity to deallocate/read itself only (${var.name_prefix})."

  permissions {
    actions = [
      "Microsoft.Compute/virtualMachines/deallocate/action",
      "Microsoft.Compute/virtualMachines/read",
    ]
    not_actions = []
  }

  assignable_scopes = ["/subscriptions/${var.subscription_id}"]
}

resource "azurerm_role_assignment" "self_deallocate" {
  for_each = local.team_vms

  scope              = azurerm_linux_virtual_machine.team[each.key].id
  role_definition_id = azurerm_role_definition.self_deallocate.role_definition_resource_id
  principal_id       = azurerm_linux_virtual_machine.team[each.key].identity[0].principal_id
}

# --- Student RBAC (both methods) ---

# Reader on the team RG: see the VM in the portal; required for `az ssh vm` to
# read VM/NIC/PublicIP metadata.
resource "azurerm_role_assignment" "rg_reader" {
  for_each = {
    for pair in local.team_member_pairs : "${pair.team}|${pair.upn}|reader" => pair
  }

  scope                = azurerm_resource_group.team[each.value.team].id
  role_definition_name = "Reader"
  principal_id         = data.azuread_user.members[each.value.upn].object_id
}

# Virtual Machine Contributor on the VM: start/stop/restart from the portal.
resource "azurerm_role_assignment" "vm_contributor" {
  for_each = {
    for pair in local.team_member_pairs : "${pair.team}|${pair.upn}|vmcontributor" => pair
  }

  scope                = azurerm_linux_virtual_machine.team[each.value.team].id
  role_definition_name = "Virtual Machine Contributor"
  principal_id         = data.azuread_user.members[each.value.upn].object_id
}

# --- Entra-only: SSH-login extension + Virtual Machine User Login role ---

resource "azurerm_virtual_machine_extension" "entra_ssh" {
  for_each = local.is_entra ? local.team_vms : {}

  name                       = "AADSSHLoginForLinux"
  virtual_machine_id         = azurerm_linux_virtual_machine.team[each.key].id
  publisher                  = "Microsoft.Azure.ActiveDirectory"
  type                       = "AADSSHLoginForLinux"
  type_handler_version       = "1.0"
  auto_upgrade_minor_version = true
  tags                       = var.tags
}

resource "azurerm_role_assignment" "vm_user_login" {
  for_each = local.is_entra ? {
    for pair in local.team_member_pairs : "${pair.team}|${pair.upn}|vmuser" => pair
  } : {}

  scope                = azurerm_linux_virtual_machine.team[each.value.team].id
  role_definition_name = "Virtual Machine User Login"
  principal_id         = data.azuread_user.members[each.value.upn].object_id
}
