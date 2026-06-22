data "local_file" "user_names" {
  filename = "./users.csv"
}

locals {
  effective_subscription_id = var.subscription_id

  groups      = csvdecode(data.local_file.user_names.content)
  group_count = length(local.groups)

  group_configs = {
    for i in range(local.group_count) : format("%02d", i + 1) => {
      index      = i
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

  team_member_pairs = flatten([
    for t, members in local.team_members : [
      for upn in members : {
        team = t
        upn  = upn
      }
    ]
  ])

  # One VM per team, keyed by team name
  team_vms = {
    for team in local.teams : team => { team = team }
  }

  # (team, upn, vm_key) triples — vm_key == team since there is one VM per team
  team_member_vm_triples = [
    for pair in local.team_member_pairs : {
      team   = pair.team
      upn    = pair.upn
      vm_key = pair.team
    }
  ]
}

data "azuread_user" "members" {
  for_each            = toset(distinct([for gm in local.group_members_flattened : gm.user_principal_name]))
  user_principal_name = each.value
}

resource "tls_private_key" "bootstrap" {
  algorithm = "RSA"
  rsa_bits  = 4096
}

resource "local_file" "private_key" {
  filename        = "${path.module}/id_rsa_lab.pem"
  content         = tls_private_key.bootstrap.private_key_openssh
  file_permission = "0600"
}

resource "local_file" "public_key" {
  filename = "${path.module}/id_rsa_lab.pub"
  content  = tls_private_key.bootstrap.public_key_openssh
}

# inventory.ini: team name is both the host alias and the group_name var,
# so deploy-keys.yml can look up keys/<group_name>.pub for each host.
resource "local_file" "ansible_inventory" {
  filename = "${path.module}/inventory.ini"
  content  = <<EOT
[vms]
%{for team, pip in azurerm_public_ip.team~}
${team} ansible_host=${pip.ip_address} group_name=${team}
%{endfor~}

[vms:vars]
ansible_user=vmadmin
ansible_ssh_private_key_file=./id_rsa_lab.pem
EOT
}

resource "local_file" "ansible_cfg" {
  filename = "${path.module}/ansible.cfg"
  content  = <<EOT
[defaults]
host_key_checking = False
inventory = ./inventory.ini
private_key_file = ./id_rsa_lab.pem
remote_user = vmadmin
roles_path = ./roles
# Target VMs are Ubuntu with python3 at a stable path — skip discovery noise.
interpreter_python = auto_silent
# Silence deprecation warnings raised inside third-party collections (e.g. ansible.posix).
deprecation_warnings = False

[ssh_connection]
ssh_args = -o IdentitiesOnly=yes
# Fewer SSH round-trips per task; safe on the Ubuntu cloud image (no requiretty).
pipelining = True
EOT
}

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

  # Port 22 open to the world — key-only auth (PasswordAuthentication no in cloud-init).
  # GitHub-hosted runners have no fixed IP, so restricting by source would block CI deploys.
  security_rule {
    name                       = "allow-ssh"
    priority                   = 100
    direction                  = "Inbound"
    access                     = "Allow"
    protocol                   = "Tcp"
    source_port_range          = "*"
    destination_port_range     = "22"
    source_address_prefix      = "Internet"
    destination_address_prefix = "*"
  }

  # Port 80: Let's Encrypt HTTP-01 challenge + HTTP→HTTPS redirect
  security_rule {
    name                       = "allow-http"
    priority                   = 105
    direction                  = "Inbound"
    access                     = "Allow"
    protocol                   = "Tcp"
    source_port_range          = "*"
    destination_port_range     = "80"
    source_address_prefix      = "Internet"
    destination_address_prefix = "*"
  }

  security_rule {
    name                       = "allow-https"
    priority                   = 110
    direction                  = "Inbound"
    access                     = "Allow"
    protocol                   = "Tcp"
    source_port_range          = "*"
    destination_port_range     = "443"
    source_address_prefix      = "Internet"
    destination_address_prefix = "*"
  }
}

resource "azurerm_public_ip" "team" {
  for_each = local.team_vms

  name                = "${var.name_prefix}-${each.key}-pip"
  location            = azurerm_resource_group.team[each.value.team].location
  resource_group_name = azurerm_resource_group.team[each.value.team].name
  allocation_method   = "Static"
  sku                 = "Standard"
  # FQDN: <name_prefix>-<team>.<region>.cloudapp.azure.com
  # Required for Let's Encrypt — certificates cannot be issued for bare IPs.
  domain_name_label   = "${var.name_prefix}-${replace(each.key, "_", "-")}"
  tags                = var.tags
}

resource "azurerm_network_interface" "team" {
  for_each = local.team_vms

  name                = "${var.name_prefix}-${each.key}-nic"
  location            = azurerm_resource_group.team[each.value.team].location
  resource_group_name = azurerm_resource_group.team[each.value.team].name
  tags                = var.tags

  ip_configuration {
    name                          = "ipconfig1"
    subnet_id                     = azurerm_subnet.team[each.value.team].id
    private_ip_address_allocation = "Dynamic"
    public_ip_address_id          = azurerm_public_ip.team[each.key].id
  }
}

resource "azurerm_network_interface_security_group_association" "team" {
  for_each = local.team_vms

  network_interface_id      = azurerm_network_interface.team[each.key].id
  network_security_group_id = azurerm_network_security_group.team[each.value.team].id
}

resource "azurerm_linux_virtual_machine" "team" {
  for_each = local.team_vms

  name                = "${var.name_prefix}-${each.key}"
  computer_name       = "${var.name_prefix}-${replace(each.key, "_", "-")}"
  resource_group_name = azurerm_resource_group.team[each.value.team].name
  location            = azurerm_resource_group.team[each.value.team].location
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

  # cloud-init creates the deploy user (no keys yet), installs Docker + Azure CLI,
  # hardens SSH, and sets up the idle-watcher systemd timer.
  custom_data = base64encode(file("${path.module}/cloud-init.yaml"))

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

  identity {
    type = "SystemAssigned"
  }
}

resource "azurerm_dev_test_global_vm_shutdown_schedule" "team" {
  for_each = var.auto_shutdown_time != "" ? local.team_vms : {}

  virtual_machine_id    = azurerm_linux_virtual_machine.team[each.key].id
  location              = azurerm_resource_group.team[each.value.team].location
  enabled               = true
  daily_recurrence_time = var.auto_shutdown_time
  timezone              = "UTC"

  notification_settings {
    enabled         = true
    email           = local.team_members[each.value.team][0]
    time_in_minutes = 30
  }

  tags = var.tags
}

# Custom role: each VM's managed identity can deallocate (and read) only itself.
# Omits 'start' deliberately — the in-guest watcher can turn the VM off but not keep it on.
resource "azurerm_role_definition" "self_deallocate" {
  name        = "vm-self-deallocate-${var.name_prefix}"
  scope       = "/subscriptions/${var.subscription_id}"
  description = "Allow a VM's managed identity to deallocate/read itself only"

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

# --- RBAC for students (Entra accounts) ---

# Reader on the team RG: lets students see the VM in the portal.
resource "azurerm_role_assignment" "rg_reader" {
  for_each = {
    for pair in local.team_member_pairs :
    "${pair.team}|${pair.upn}|reader" => pair
  }

  scope                = azurerm_resource_group.team[each.value.team].id
  role_definition_name = "Reader"
  principal_id         = data.azuread_user.members[each.value.upn].object_id
}

# Virtual Machine Contributor on the VM: lets students start/stop/restart from the portal.
# (No Entra SSH — students connect as the 'deploy' user with plain SSH key-pair auth.)
resource "azurerm_role_assignment" "vm_contributor" {
  for_each = {
    for triple in local.team_member_vm_triples :
    "${triple.vm_key}|${triple.upn}|vmcontributor" => triple
  }

  scope                = azurerm_linux_virtual_machine.team[each.value.vm_key].id
  role_definition_name = "Virtual Machine Contributor"
  principal_id         = data.azuread_user.members[each.value.upn].object_id
}
