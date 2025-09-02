terraform state list \
  | grep '^databricks_user\.workspace_user\["group_' \
  | while read addr; do
      terraform state rm "$addr"
    done

