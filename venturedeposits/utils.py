import resend
import logging
from datetime import datetime

from django.template.loader import render_to_string

logger = logging.getLogger(__name__)

current_year = datetime.now().year


def send_venture_deposit_made_email(member, venture_deposit):
    try:
        email_body = render_to_string(
            "venture_deposit_made.html",
            {
                "member": member,
                "venture_deposit": venture_deposit,
                "current_year": current_year,
            },
        )
        params = {
            "from": "SACCO <finance@wananchimali.com>",
            "to": [member.email],
            "subject": "Venture Purchase Confirmation",
            "html": email_body,
        }
        response = resend.Emails.send(params)
        logger.info(f"Email sent to {member.email} with response: {response}")
        return response
    except Exception as e:
        logger.error(f"Error sending email to {member.email}: {str(e)}")
        return None
