from databricks.resource_manager.user_mail import send_emails

if __name__ == "__main__":
    send_emails("test subject", "message body",recipients = ["noam1023@gmail.com", 'cnoam@technion.ac.il', 'efrat.mimon@technion.ac.il'] )

