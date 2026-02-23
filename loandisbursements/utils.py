import resend
import logging
from datetime import datetime

from django.template.loader import render_to_string

logger = logging.getLogger(__name__)

current_year = datetime.now().year


def send_disbursement_made_email(user, disbursement):
    try:
        email_body = render_to_string(
            "disbursement_made.html",
            {"user": user, "disbursement": disbursement, "current_year": current_year},
        )
        params = {
            "from": "Tamarind SACCO <finance@wananchimali.com>",
            "to": [user.email],
            "subject": "Disbursement Confirmation",
            "html": email_body,
        }
        response = resend.Emails.send(params)
        logger.info(f"Email sent to {user.email} with response: {response}")
        return response
    except Exception as e:
        logger.error(f"Error sending email to {user.email}: {str(e)}")
        return None
