# Generate Ansible inventory + config into the COURSE ROOT (path.root), so each
# course folder is self-contained: its own inventory.ini, ansible.cfg, key, and
# keys/ dir. Always run ansible from inside the course folder.
#
# Host alias carries name_prefix so a wrong-folder run is obvious in the play
# recap. group_name=<team> lets deploy-keys.yml look up keys/<team>.pub.

resource "local_file" "ansible_inventory" {
  filename = "${path.root}/inventory.ini"
  content  = <<-EOT
    [vms]
    %{for team, pip in azurerm_public_ip.team~}
    ${var.name_prefix}-${team} ansible_host=${pip.ip_address} group_name=${team}
    %{endfor~}

    [vms:vars]
    ansible_user=vmadmin
    ansible_ssh_private_key_file=./id_rsa_lab.pem
  EOT
}

resource "local_file" "ansible_cfg" {
  filename = "${path.root}/ansible.cfg"
  content  = <<-EOT
    [defaults]
    inventory          = ./inventory.ini
    private_key_file   = ./id_rsa_lab.pem
    remote_user        = vmadmin
    roles_path         = ../../ansible/roles
    host_key_checking  = False
    # Ubuntu cloud image has python3 at a stable path — skip discovery noise.
    interpreter_python = auto_silent
    # Silence deprecation warnings raised inside third-party collections.
    deprecation_warnings = False

    [ssh_connection]
    ssh_args = -o IdentitiesOnly=yes
    # Fewer SSH round-trips per task; safe on the Ubuntu cloud image (no requiretty).
    pipelining = True
  EOT
}
