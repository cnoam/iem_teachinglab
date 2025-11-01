output "student_groups" {
  description = "Map of created student groups keyed by group name"
  value       = databricks_group.student_groups
}

output "all_student_groups" {
  description = "The group containing all student groups"
  value       = databricks_group.all_student_groups
}