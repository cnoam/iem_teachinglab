#!/bin/bash
# export notbooks from databricks workspace to local disk.
# must have 'databricks' cli tool installed, and  the profile created with host and token.

# script created by Gemini 2025-11-27

# Configuration
PROFILE="old_eastus2"
LOCAL_BACKUP_DIR="./databricks_backup.$PROFILE"

echo "--- Starting Export from $PROFILE ---"
echo "writing to $LOCAL_BACKUP_DIR"

# Create local backup directory if it doesn't exist
mkdir -p "$LOCAL_BACKUP_DIR/Shared"
mkdir -p "$LOCAL_BACKUP_DIR/Users"

# 1. Export Shared Workspace
# We use --overwrite to ensure we get the latest if you run this multiple times
echo "Exporting /Shared..."
databricks workspace export-dir /Shared "$LOCAL_BACKUP_DIR/Shared" --profile $PROFILE --overwrite

# 2. Export All Users
# This grabs the entire structure under /Users recursively
echo "Exporting /Users (All Users)..."
databricks workspace export-dir /Users "$LOCAL_BACKUP_DIR/Users" --profile $PROFILE --overwrite

echo "--- Export Complete. Files saved in $LOCAL_BACKUP_DIR ---"
