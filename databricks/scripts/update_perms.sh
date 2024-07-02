#!/bin/sh -xu
curl --request PUT \
"https://${DATABRICKS_HOST}/api/2.0/permissions/clusters/0626-112702-5gj1668f"  \
--header "Authorization: Bearer ${DATABRICKS_TOKEN}"  \
--data '{"access_control_list": [{"group_name": "g1", "permission_level": "CAN_RESTART"}]}'