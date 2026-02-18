import resend
from datetime import datetime
from decimal import Decimal
from guaranteerequests.models import GuaranteeRequest

current_year = datetime.now().year


from django.template.loader import render_to_string
import logging

logger = logging.getLogger(__name__)

def send_guarantor_guarantee_request_status_email(guarantee_request: GuaranteeRequest):
    """
    Notify the guarantor of a request made to them by the member applying for a loan
    """
    guarantor = guarantee_request.guarantor.member
    applicant = guarantee_request.loan_application.member
    application = guarantee_request.loan_application
    amount = guarantee_request.guaranteed_amount
    
    email_body = ""

    try:
        email_body = render_to_string(
            "guarantee_request_notification.html",
            {
                "guarantor": guarantor,
                "applicant": applicant,
                "application": application,
                "amount": amount,
                "current_year": current_year,
            },
        )
        params = {
            "from": "SACCO <notifications@wananchimali.com>",
            "to": [guarantor.email],
            "subject": "New Guarantee Request",
            "html": email_body,
        }
        response = resend.Emails.send(params)
        logger.info(f"Guarantee request email sent to {guarantor.email} with response: {response}")
        return response

    except Exception as e:
        logger.error(f"Error sending guarantee request email to {guarantor.email}: {str(e)}")
        return None

def send_guarantee_request_status_email(guarantee_request: GuaranteeRequest):
    """
    Notify the member applying for a loan of the status of their guarantee request
    """
    guarantor = guarantee_request.guarantor.member
    applicant = guarantee_request.loan_application.member
    application = guarantee_request.loan_application
    status = guarantee_request.status
    amount = guarantee_request.guaranteed_amount
    
    email_body = ""

    try:
        email_body = render_to_string(
            "guarantee_request_status.html",
            {
                "guarantor": guarantor,
                "applicant": applicant,
                "application": application,
                "status": status,
                "amount": amount,
                "current_year": current_year,
            },
        )
        params = {
            "from": "SACCO <notifications@wananchimali.com>",
            "to": [applicant.email],
            "subject": f"Guarantee Request Update - {status}",
            "html": email_body,
        }
        response = resend.Emails.send(params)
        logger.info(f"Guarantee status email sent to {applicant.email} with response: {response}")
        return response

    except Exception as e:
        logger.error(f"Error sending guarantee status email to {applicant.email}: {str(e)}")
        return None