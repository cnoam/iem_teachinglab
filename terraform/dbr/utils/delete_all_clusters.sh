#!/bin/sh -xu
PROF="old_eastus2"
databricks clusters list --profile $PROF --output JSON \
   | jq -r '.[].cluster_id'  > clusters_$PROF

cat clusters_$PROF | xargs -I {} databricks --profile $PROF --debug clusters unpin {}
cat clusters_$PROF| xargs -I {} databricks --profile $PROF --debug clusters permanent-delete {}

 
