#!/bin/sh 
PROF="old_eastus2"
databricks users list --profile $PROF --output JSON  \
  | jq -r '.[] | select(.userName != "cnoam@technion.ac.il") | .id' > users_w_to_delete

#  | xargs -I {} databricks --profile $PROF users delete  {}
