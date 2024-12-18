"""
we want to send warning to the user. find her email.

cluster30 --> g_30 --> cnoam@here.com
"""
import logging
import os
import time

dry_run = False

def send_emails_google(subject:str, body: str, recipients: list[str]):
    import smtplib
    from email.mime.text import MIMEText
    sender = "dds.lab.technion@gmail.com"
    # When using gmail, generate an application password.
    # see https://support.google.com/accounts/answer/185833?hl=en
    password = os.getenv("SMTP_PASSWORD")
    assert(password and len(password) > 6)
    msg = MIMEText(body)
    msg['Subject'] = subject
    msg['From'] = sender
    msg['To'] = ', '.join(recipients)
    msg['CC'] = os.getenv('ADMIN_EMAIL')
    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp_server:
        smtp_server.login(sender, password)
        smtp_server.sendmail(sender, recipients, msg.as_string())


def send_emails_azure(subject:str, body_html: str, recipients: list[str], logger: logging.Logger|None):
    """Send email using Azure service.
    This service must be configured prior to calling. After configuration, an API key is supplied.
    This key must be saved in AZURE_EMAIL_ACCESS_KEY env var
    """
    from azure.communication.email import EmailClient

    key = os.getenv('AZURE_EMAIL_ACCESS_KEY')
    if not key:
        raise EnvironmentError("env var AZURE_EMAIL_ACCESS_KEY must be defined")
    admin_email = os.getenv('ADMIN_EMAIL')
    from_ = "DoNotReply@de9384ea-2d1f-4d24-a721-44bab6f65b6f.azurecomm.net"   # <<< HARD CODED

    connection_string = f"endpoint=https://comm-servicenc.unitedstates.communication.azure.com/;accesskey={key}"
    client = EmailClient.from_connection_string(connection_string)

    recipients_list = [{'address': v} for v in recipients]
    admin_list = [{'address': admin_email }]
    message = {
        "senderAddress": from_,
        "recipients": {
            "to": recipients_list,
            "cc": admin_list
        },
        "content": {
            "subject": subject,
            "html": body_html
        }
    }

    global dry_run
    if dry_run:
        print(f"FAKE sending mail to {recipients_list}, {admin_list}")
        result = None
    else:
        start = time.time()
        poller = client.begin_send(message)
        if logger:
            logger.info(f"Sending email took {time.time()-start:.2f} seconds")
        start = time.time()
        result = poller.result()
        if logger:
            logger.info(f"waiting for email result took {time.time()-start:.2f} seconds")
    return result


def send_emails(subject:str, body: str, recipients: list[str], logger):
    return send_emails_azure(subject,body,recipients,logger)
