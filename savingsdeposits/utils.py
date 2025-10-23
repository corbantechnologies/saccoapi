import resend
import logging
from datetime import datetime

from django.template.loader import render_to_string

logger = logging.getLogger(__name__)

current_year = datetime.now().year


def send_deposit_made_email(user, deposit):
    try:
        email_body = render_to_string(
            "deposit_made.html",
            {"user": user, "deposit": deposit, "current_year": current_year},
        )
        params = {
            "from": "SACCO <finance@wananchimali.com>",
            "to": [user.email],
            "subject": "Deposit Confirmation",
            "html": email_body,
        }
        response = resend.Emails.send(params)
        logger.info(f"Email sent to {user.email} with response: {response}")
        return response
    except Exception as e:
        logger.error(f"Error sending email to {user.email}: {str(e)}")
        return None
