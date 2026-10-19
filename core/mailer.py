"""
mailer.py
---------
Sends the "reset your password" email using Gmail's SMTP server.

Needs two environment variables set in Vercel:
  SMTP_EMAIL         - the Gmail address sending the email
  SMTP_APP_PASSWORD  - a 16-character "App Password" generated from that
                       Google account (not the normal Gmail password).
                       See README.md for how to generate one.
"""

import os
import smtplib
import ssl
from email.mime.text import MIMEText


def send_reset_email(to_email: str, reset_link: str):
    sender = os.environ["SMTP_EMAIL"]
    app_password = os.environ["SMTP_APP_PASSWORD"]

    body = f"""Hello,

We received a request to reset your StockSetu password.

Click this link to set a new password (valid for 1 hour):
{reset_link}

If you didn't ask for this, you can safely ignore this email.

- StockSetu
"""
    msg = MIMEText(body)
    msg["Subject"] = "Reset your StockSetu password"
    msg["From"] = sender
    msg["To"] = to_email

    context = ssl.create_default_context()
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=context) as server:
        server.login(sender, app_password)
        server.sendmail(sender, to_email, msg.as_string())
