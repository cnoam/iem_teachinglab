#!/bin/sh -xu
echo "Create a new DBR group"

curl --request POST \
"https://${DATABRICKS_HOST}/api/2.0/preview/scim/v2/Groups"  \
--header "Authorization: Bearer ${DATABRICKS_TOKEN}" \
--data '{  "displayName": "I am test grup", "groups": [ {"value":"g33", "display":" g 22 disp", "primary": true}]  }'
echo "*******"