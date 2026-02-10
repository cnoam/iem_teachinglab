data "local_file" "user_names" {
  filename = "./users.csv"
}



locals {
  # Prefer explicit input, otherwise use the subscription from the current Azure CLI login.
  effective_subscription_id = var.subscription_id

  # Parse the CSV into a list of maps, where each map is a group of students
  groups = csvdecode(data.local_file.user_names.content)

  # Number of groups, derived from the CSV file
  group_count = length(local.groups)

  # Create a map where keys are "01", "02", etc., and values are objects
  # containing all names for that logical group.
  group_configs = {
    for i in range(local.group_count) : format("%02d", i + 1) => {
      index                  = i
      group_name             = format("group_%02d", i + 1)
    }
  }

  # Flattened list of student members and their assigned group names (from CSV)
  group_members_flattened = flatten([
    for idx, group in local.groups : [
      for member in group : {
        group               = local.group_configs[format("%02d", idx + 1)].group_name
        user_principal_name = trimspace(member)
      } if trimspace(member) != "" # Filter out empty member names
    ]
  ])

  teams = distinct([for gm in local.group_members_flattened : gm.group])

  team_members = {
    for t in local.teams :
    t => distinct([for gm in local.group_members_flattened : gm.user_principal_name if gm.group == t])
  }

  # Flatten (team, member) pairs for RBAC assignments
  team_member_pairs = flatten([
    for t, members in local.team_members : [
      for upn in members : {
        team = t
        upn  = upn
      }
    ]
  ])
}


# Lookup Entra users (UPN -> objectId) for RBAC.
# Requires directory read permissions for the Terraform identity.
data "azuread_user" "members" {
  for_each            = toset(distinct([for gm in local.group_members_flattened : gm.user_principal_name]))
  user_principal_name = each.value
}

resource "tls_private_key" "bootstrap" {
  algorithm = "RSA"
  rsa_bits  = 4096
}

# Write the VM admin SSH keypair to disk for easy use.
resource "local_file" "vmadmin_private_key" {
  filename = "${path.module}/vmadmin_id_rsa"
  content  = tls_private_key.bootstrap.private_key_pem
}

resource "local_file" "vmadmin_public_key" {
  filename = "${path.module}/vmadmin_id_rsa.pub"
  content  = tls_private_key.bootstrap.public_key_openssh
}

# Create one RG per team (recommended for clean isolation)
resource "azurerm_resource_group" "team" {
  for_each = local.team_members

  name     = "${var.name_prefix}-${each.key}"
  location = var.location
}

resource "azurerm_virtual_network" "team" {
  for_each = local.team_members

  name                = "${var.name_prefix}-${each.key}-vnet"
  location            = azurerm_resource_group.team[each.key].location
  resource_group_name = azurerm_resource_group.team[each.key].name
  address_space       = ["10.${100 + index(local.teams, each.key)}.0.0/16"]
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
}

resource "azurerm_public_ip" "team" {
  for_each = local.team_members

  name                = "${var.name_prefix}-${each.key}-pip"
  location            = azurerm_resource_group.team[each.key].location
  resource_group_name = azurerm_resource_group.team[each.key].name
  allocation_method   = "Static"
  sku                 = "Standard"
}

resource "azurerm_network_interface" "team" {
  for_each = local.team_members

  name                = "${var.name_prefix}-${each.key}-nic"
  location            = azurerm_resource_group.team[each.key].location
  resource_group_name = azurerm_resource_group.team[each.key].name

  ip_configuration {
    name                          = "ipconfig1"
    subnet_id                     = azurerm_subnet.team[each.key].id
    private_ip_address_allocation = "Dynamic"
    public_ip_address_id          = azurerm_public_ip.team[each.key].id
  }
}

resource "azurerm_network_interface_security_group_association" "team" {
  for_each = local.team_members

  network_interface_id      = azurerm_network_interface.team[each.key].id
  network_security_group_id = azurerm_network_security_group.team[each.key].id
}

resource "azurerm_linux_virtual_machine" "team" {
  for_each = local.team_members

  name                = "${var.name_prefix}-${each.key}-vm"
  computer_name  = "${var.name_prefix}-${replace(each.key, "_", "-")}-vm"
  resource_group_name = azurerm_resource_group.team[each.key].name
  location            = azurerm_resource_group.team[each.key].location
  size                = var.vm_size

  admin_username                  = "vmadmin"
  disable_password_authentication = true

  network_interface_ids = [
    azurerm_network_interface.team[each.key].id
  ]

  admin_ssh_key {
    username   = "vmadmin"
    public_key = tls_private_key.bootstrap.public_key_openssh
  }

  os_disk {
    caching              = "ReadWrite"
    storage_account_type = "Standard_LRS"
  }

  source_image_reference {
    publisher = "Canonical"
    offer     = "0001-com-ubuntu-server-jammy"
    sku       = var.ubuntu_sku
    version   = "latest"
  }

  identity {
    type = "SystemAssigned"
  }
}

# Enable Microsoft Entra ID (Azure AD) SSH login via VM extension.
# This installs the aadsshlogin packages used for Entra SSH auth. See Microsoft Learn.
resource "azurerm_virtual_machine_extension" "entra_ssh" {
  for_each = local.team_members

  name                       = "AADSSHLoginForLinux"
  virtual_machine_id         = azurerm_linux_virtual_machine.team[each.key].id
  publisher                  = "Microsoft.Azure.ActiveDirectory"
  type                       = "AADSSHLoginForLinux"
  type_handler_version       = "1.0"
  auto_upgrade_minor_version = true
}

# After provisioning is complete, deallocate the VMs to avoid compute costs.
# This depends on the VM extension so we only stop once the VM is fully ready.
resource "null_resource" "stop_vm" {
  for_each = local.team_members

  triggers = {
    vm_id      = azurerm_linux_virtual_machine.team[each.key].id
    extension  = azurerm_virtual_machine_extension.entra_ssh[each.key].id
  }

  provisioner "local-exec" {
    command = "az vm deallocate --ids ${azurerm_linux_virtual_machine.team[each.key].id}"
  }
}

# --- RBAC assignments ---
# Reader on the team RG: required for 'az ssh vm' to read VM/NIC/PublicIP metadata via ARM.
resource "azurerm_role_assignment" "rg_reader" {
  for_each = {
    for pair in local.team_member_pairs :
    "${pair.team}|${pair.upn}|reader" => pair
  }

  scope                = azurerm_resource_group.team[each.value.team].id
  role_definition_name = "Reader"
  principal_id         = data.azuread_user.members[each.value.upn].object_id
}

# Virtual Machine User Login on the VM: authorizes Entra-based SSH login.
resource "azurerm_role_assignment" "vm_user_login" {
  for_each = {
    for pair in local.team_member_pairs :
    "${pair.team}|${pair.upn}|vmuser" => pair
  }

  scope                = azurerm_linux_virtual_machine.team[each.value.team].id
  role_definition_name = "Virtual Machine User Login"
  principal_id         = data.azuread_user.members[each.value.upn].object_id
}
# gemini 2026-02-10 13:30
