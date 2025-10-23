import resend
import logging
from datetime import datetime

from django.template.loader import render_to_string

logger = logging.getLogger(__name__)

current_year = datetime.now().year


def send_venture_payment_confirmation_email(member, venture_payment):
    email_body = ""
    current_year = datetime.now().year

    try:
        email_body = render_to_string(
            "venture_payment_confirmation.html",
            {
                "member": member,
                "venture_payment": venture_payment,
                "current_year": current_year,
            },
        )
        params = {
            "from": "SACCO <finance@wananchimali.com>",
            "to": [member.email],
            "subject": "Payment Confirmation",
            "html": email_body,
        }
        response = resend.Emails.send(params)
        logger.info(f"Email sent to {member.email} with response: {response}")
        return response

    except Exception as e:
        logger.error(f"Error sending email to {member.email}: {str(e)}")
        return None


def send_venture_payment_update_email(member, venture_payment):
    try:
        email_body = render_to_string(
            "venture_payment_update.html",
            {
                "member": member,
                "venture_payment": venture_payment,
                "current_year": current_year,
            },
        )
        params = {
            "from": "SACCO <finance@wananchimali.com>",
            "to": [member.email],
            "subject": "Venture Payment Update",
            "html": email_body,
        }
        response = resend.Emails.send(params)
        logger.info(f"Email sent to {member.email} with response: {response}")
        return response
    except Exception as e:
        logger.error(f"Error sending email to {member.email}: {str(e)}")
        return None
