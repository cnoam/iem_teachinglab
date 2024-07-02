#!/bin/sh -xu
curl --request GET \
"https://${DATABRICKS_HOST}/api/2.0/permissions/clusters/?cluster_id=0626-112702-5gj1668f"  \
--header "Authorization: Bearer ${DATABRICKS_TOKEN}" 
