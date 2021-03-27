import smtplib, ssl, os

email_from = os.environ.get('EMAIL_FROM')
email_to = os.environ.get('EMAIL_TO')
email_pw = os.environ.get('EMAIL_PW')


port = 587  # For starttls
smtp_server = "smtp.gmail.com"
sender_email = email_from
receiver_email = email_to
message = """\
Subject: PV - Anlage

This message is sent from Python."""

context = ssl.create_default_context()
with smtplib.SMTP(smtp_server, port) as server:
    server.ehlo()  # Can be omitted
    server.starttls(context=context)
    server.ehlo()  # Can be omitted
    server.login(sender_email, email_pw)
    server.sendmail(sender_email, receiver_email.split(','), message)

