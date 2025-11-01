# Users Module

This module creates Databricks users based on a list of email addresses.

## Variables

- `users` - List of user email addresses to create
- `workspace_access` - Whether to grant workspace access to users (default: false)
- `active` - Whether the users should be active (default: true)

## Outputs

- `users` - Map of created users keyed by email address