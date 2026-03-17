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

# Mock RBAC assignments — fake principal can't be assigned real roles.
override_resource {
  target = azurerm_role_assignment.rg_reader
  values = {
    id = "/mock/role-assignment/rg-reader"
  }
}

override_resource {
  target = azurerm_role_assignment.vm_user_login
  values = {
    id = "/mock/role-assignment/vm-user-login"
  }
}

# Mock VM extension — AADSSHLoginForLinux takes ~15 min to provision and is not
# under test here. Mocking it keeps the deploy run to ~5 min.
override_resource {
  target = azurerm_virtual_machine_extension.entra_ssh
  values = {
    id = "/mock/vm-extension/entra-ssh"
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

# Deploys real VMs (~5 min). RBAC and VM extension are mocked.
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
    condition     = contains(keys(output.team_public_ip_addresses), "group_01")
    error_message = "No public IP address found for group_01 VM."
  }
}
