# Mock the CSV file with a valid header + one team row
override_data {
  target = data.local_file.user_names
  values = {
    content = "user1,user2,user3,user4\ntestuser1@example.com,testuser2@example.com,,\n"
  }
}

# Mock Entra user lookup — the fake object_id doesn't exist in the real directory,
# so RBAC assignments that reference it must also be mocked (see below).
override_data {
  target = data.azuread_user.members
  values = {
    object_id           = "00000000-0000-0000-0000-000000000001"
    user_principal_name = "testuser1@example.com"
  }
}

# Mock RBAC assignments that use the fake Entra principal.
override_resource {
  target = azurerm_role_assignment.rg_reader
  values = {
    id = "/mock/role-assignment/rg-reader"
  }
}

override_resource {
  target = azurerm_role_assignment.vm_contributor
  values = {
    id = "/mock/role-assignment/vm-contributor"
  }
}

variables {
  name_prefix     = "tftest"
  location        = "eastus"
  subscription_id = "b3931bf1-b901-4dc2-bf3e-b020fa67cb8b"
  tags = {
    project     = "iem-teachinglab"
    managed_by  = "terraform"
    environment = "terraform-test"
  }
}

# Deploys real VMs (~5 min). RBAC assignments for Entra users are mocked.
# For SSH / cloud-init verification run: bash tests/verify_ssh.sh
run "deploy_and_verify" {
  command = apply

  assert {
    condition     = local_file.private_key.content != null
    error_message = "SSH private key (id_rsa_lab.pem) was not written to disk."
  }

  assert {
    condition     = strcontains(local_file.ansible_inventory.content, "group_01")
    error_message = "Ansible inventory does not contain group_01."
  }

  assert {
    condition     = strcontains(local_file.ansible_inventory.content, "group_name=group_01")
    error_message = "Ansible inventory is missing the group_name host var for group_01."
  }

  assert {
    condition     = contains(keys(output.team_public_ip_addresses), "group_01")
    error_message = "No public IP address found for group_01."
  }

  assert {
    condition     = contains(keys(output.vm_fqdns), "group_01")
    error_message = "No FQDN found for group_01."
  }
}
