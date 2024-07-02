#!/bin/sh -xu
curl --request PATCH \
"https://${DATABRICKS_HOST}/api/2.0/preview/scim/v2/Users"  \
--header "Authorization: Bearer ${DATABRICKS_TOKEN}" \
--data '{ "userName": "tester2@box.org", "active": true , "displayName": "I am tester"  }'
echo "*******"