#!/bin/bash -eux

# Subdomain (send only) keys:
export MAILJET_API_KEY=""
export MAILJET_SECRET_KEY=""



curl -s \
	-X POST \
	--user "$MAILJET_API_KEY:$MAILJET_SECRET_KEY" \
	https://api.mailjet.com/v3/send \
	-H 'Content-Type: application/json' \
	-d '{
      "FromEmail":"noam1023@gmail.com",
      "FromName":"Noam Cohen",
      "Recipients":[
        {
          "Email":"cnoam@technion.ac.il",
          "Name":"Passenger 2"
        },
        {
          "Email":"noam1023@gmail.com",
          "Name":"Passenger 3"
        }
      ],
      "Subject":"Your email flight plan( MAIN KEY)4!",
      "Text-part":"Dear passenger, welcome to Mailjet! May the delivery force be with you!",
      "Html-part":"<h3>Dear passenger, welcome to Mailjet!</h3><br />May the delivery force be with you!"
	}'
