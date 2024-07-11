#/bin/bash -eu
# create a sender email in Mailjet.
# This is mandatory before can send mail
# After creation, MUST validate the user id

# 2024-07-04 09:55
export MAILJET_API_KEY=""
export MAILJET_SECRET_KEY=""
curl -s \
	-X POST \
	--user "$MAILJET_API_KEY:$MAILJET_SECRET_KEY" \
	https://api.mailjet.com/v3/REST/sender/validate \
	-H 'Content-Type: application/json' \
	-d '{
      "EmailType":"bulk",
      "IsDefaultSender":"true",
      "Name":"scripts",
      "Email":"cnoam@technion.ac.il"
	}'