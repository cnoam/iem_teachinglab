# Groups Module

This module creates Databricks groups and manages group memberships.

## Variables

- `group_names` - List of group names to create
- `all_student_groups_name` - Name for the group that contains all student groups (default: "all_student_groups")
- `databricks_sql_access` - Whether to grant Databricks SQL access to the all students group (default: true)
- `workspace_access` - Whether to grant workspace access to the all students group (default: true)
- `users` - Map of users created by the users module
- `group_members` - List of objects containing group_name and member_name mappings

## Outputs

- `student_groups` - Map of created student groups keyed by group name
- `all_student_groups` - The group containing all student groups