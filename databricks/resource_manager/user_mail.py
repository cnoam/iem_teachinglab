"""
we want to send warning to the user. find her email.

cluster30 --> g_30 --> cnoam@here.com
"""

import os
from databricks.DataBricksGroups import DataBricksGroups

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

def send_emails(subject:str, body: str, recipients: list[str]):
    import smtplib
    from email.mime.text import MIMEText
    #mx_record = "technion-ac-il.mail.protection.outlook.com"
    #host = "tx.technion.ac.il"
    #username = "dds.lab@technion.ac.il"
    sender = "dds.lab.technion@gmail.com"
    password = "nvexibmqakecgigl"

    msg = MIMEText(body)
    msg['Subject'] = subject
    msg['From'] = sender
    msg['To'] = ', '.join(recipients)
    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp_server:
        smtp_server.login(sender, password)
        smtp_server.sendmail(sender, recipients, msg.as_string())


if __name__ == "__main__":
    send_emails("test subject", "message body",recipients = ["noam1023@gmail.com", "cnoam@technion.ac.il"] )

