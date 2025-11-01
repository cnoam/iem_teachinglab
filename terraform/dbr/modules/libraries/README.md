# Libraries Module

This module installs required libraries on the clusters.

## Variables

- `clusters` - Map of clusters created by the clusters module
- `maven_packages` - Maven packages to install (default: {})
- `python_packages` - Python packages to install (default: [])

## Outputs

- `maven_libraries` - Map of installed Maven libraries
- `python_libraries` - Map of installed Python libraries