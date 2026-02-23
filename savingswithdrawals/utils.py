import resend
import logging
from datetime import datetime

from django.template.loader import render_to_string

logger = logging.getLogger(__name__)

current_year = datetime.now().year

# create email sending function to notify user of withdrawal


def send_withdrawal_request_email(user, withdrawal):
    """
    Sent to the client
    """
    email_body = ""
    current_year = datetime.now().year

    try:
        email_body = render_to_string(
            "withdrawal_request.html",
            {"user": user, "withdrawal": withdrawal, "current_year": current_year},
        )
        params = {
            "from": "Tamarind SACCO <finance@wananchimali.com>",
            "to": [user.email],
            "subject": "Withdrawal Request",
            "html": email_body,
        }
        response = resend.Emails.send(params)
        logger.info(f"Email sent to {user.email} with response: {response}")
        return response

    except Exception as e:
        logger.error(f"Error sending email to {user.email}: {str(e)}")
        return None


def send_withdrawal_status_email(user, withdrawal):
    email_body = ""
    current_year = datetime.now().year

    try:
        email_body = render_to_string(
            "withdrawal_status.html",
            {"user": user, "withdrawal": withdrawal, "current_year": current_year},
        )
        params = {
            "from": "Tamarind SACCO <finance@wananchimali.com>",
            "to": [user.email],
            "subject": "Withdrawal Status",
            "html": email_body,
        }
        response = resend.Emails.send(params)
        logger.info(f"Email sent to {user.email} with response: {response}")
        return response

    except Exception as e:
        logger.error(f"Error sending email to {user.email}: {str(e)}")
        return None
