# Permissions Module

This module assigns permissions to groups for their respective clusters.

## Variables

- `student_groups` - Map of student groups created by the groups module
- `clusters` - Map of clusters created by the clusters module
- `permission_level` - Permission level to assign to groups (default: "CAN_RESTART")

## Outputs

- `cluster_permissions` - Map of cluster permissions keyed by group name