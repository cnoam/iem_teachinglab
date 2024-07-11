"""
we want to send warning to the user. find her email.

cluster30 --> g_30 --> cnoam@here.com
"""

import os
from mailjet_rest import Client


from ..DataBricksGroups import DataBricksGroups
from dotenv import load_dotenv

load_dotenv()
host = 'https://' + os.getenv('DATABRICKS_HOST')
token = os.getenv('DATABRICKS_TOKEN')
dbr_groups = DataBricksGroups(host=host, token=token)


# {'members': [{'user_name': 'mdana@campus.technion.ac.il'}, {'user_name': 'liat.tsipory@campus.technion.ac.il'}]}
def get_emails_address(cluster_name: str) -> list:
    """ The cluster name MUST be 'cluster_NNN'
    """
    addr = []
    for m in dbr_groups.get_group_members("g" + cluster_name[8:]):
        addr.append(m['user_name'])
    return addr

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
    msg['CC'] = 'cnoam@technion.ac.il'
    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp_server:
        smtp_server.login(sender, password)
        smtp_server.sendmail(sender, recipients + ['cnoam@technion.ac.il'], msg.as_string())


def send_emails_azure(subject:str, body: str, recipients: list[str]):
    from azure.communication.email import EmailClient

    key  = os.getenv('AZURE_EMAIL_ACCESS_KEY')
    from_ = "DoNotReply@de9384ea-2d1f-4d24-a721-44bab6f65b6f.azurecomm.net"

    connection_string = f"endpoint=https://comm-servicenc.unitedstates.communication.azure.com/;accesskey={key}"
    client = EmailClient.from_connection_string(connection_string)

    # [{"address": "cnoam@technion.ac.il"}]
    recipients_list = [{'address': v} for v in recipients]

    message = {
        "senderAddress": from_,
        "recipients": {
            "to": recipients_list,
        },
        "content": {
            "subject": subject,
            "plainText": body,
        }
    }

    poller = client.begin_send(message)
    result = poller.result()


def send_emails(subject:str, body: str, recipients: list[str])->None:
    return send_emails_azure(subject,body,recipients)
