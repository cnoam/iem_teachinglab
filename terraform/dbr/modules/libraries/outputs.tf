output "maven_libraries" {
  description = "Map of installed Maven libraries"
  value       = databricks_library.maven_library
}

output "python_libraries" {
  description = "Map of installed Python libraries"
  value       = databricks_library.python_library
}