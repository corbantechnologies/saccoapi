import resend
from datetime import datetime
from decimal import Decimal
from django.db import models
from savings.models import SavingsAccount
from loans.models import LoanAccount
from loanapplications.models import LoanApplication
from guaranteerequests.models import GuaranteeRequest
from django.template.loader import render_to_string
from saccoapi.settings import DOMAIN
import logging

logger = logging.getLogger(__name__)

current_year = datetime.now().year


def compute_loan_coverage(application: LoanApplication) -> dict:
    total_savings = Decimal(
        SavingsAccount.objects.filter(member=application.member).aggregate(
            t=models.Sum("balance")
        )["t"]
        or "0"
    )

    # Committed self-guarantee from OTHER applications
    committed_self_other = Decimal(
        GuaranteeRequest.objects.filter(
            guarantor__member=application.member,
            status="Accepted",
            loan_application__status__in=["Submitted", "Approved", "Disbursed"],
        )
        .exclude(loan_application=application)
        .aggregate(t=models.Sum("guaranteed_amount"))["t"]
        or "0"
    )

    # THIS application's self-guarantee
    self_guarantee_this = Decimal(str(application.self_guaranteed_amount or 0))

    # Available = total savings - committed by others
    available_self = max(Decimal("0"), total_savings - committed_self_other)

    # External guarantees
    total_guaranteed_by_others = Decimal(
        application.guarantors.filter(status="Accepted").aggregate(
            t=models.Sum("guaranteed_amount")
        )["t"]
        or "0"
    )

    # Effective coverage = committed guarantees (self + others)
    effective_coverage = self_guarantee_this + total_guaranteed_by_others

    remaining_to_cover = max(
        Decimal("0"), Decimal(str(application.requested_amount)) - effective_coverage
    )
    is_fully_covered = remaining_to_cover <= Decimal("0")

    return {
        "total_savings": float(total_savings),
        "committed_self_guarantee": float(committed_self_other),
        "available_self_guarantee": float(available_self),
        "total_guaranteed_by_others": float(total_guaranteed_by_others),
        "effective_coverage": float(effective_coverage),
        "remaining_to_cover": float(remaining_to_cover),
        "is_fully_covered": is_fully_covered,
    }


def send_loan_application_status_email(application: LoanApplication):
    # notifying members of the loan application status:
    # - when it is created
    # - when it has been amended and ready to request for guarantors if not fully covered
    # - when it is fully covered and ready to be approved
    # - when it is approved and ready to be disbursed
    # - when it is disbursed
    # - when it is rejected
    
    user = application.member
    status = application.status
    email_body = ""
    
    try:
        email_body = render_to_string(
            "loan_application_status.html",
            {
                "user": user,
                "application": application,
                "status": status,
                "current_year": current_year,
            },
        )
        params = {
            "from": "SACCO <notifications@wananchimali.com>",
            "to": [user.email],
            "subject": f"Loan Application Update - {status}",
            "html": email_body,
        }
        response = resend.Emails.send(params)
        logger.info(f"Loan status email sent to {user.email} with response: {response}")
        return response

    except Exception as e:
        logger.error(f"Error sending loan status email to {user.email}: {str(e)}")
        return None

def send_admin_loan_application_status_email(application: LoanApplication):
    # notifying admin of the loan application status:
    # - when it is submitted for amendment
    # - when it is submitted for approval
    
    user = application.member
    status = application.status
    # TODO: Configure admin email in settings
    admin_email = "corbantechnologies@gmail.com" 
    email_body = ""

    try:
        email_body = render_to_string(
            "admin_loan_application_notification.html",
            {
                "user": user,
                "application": application,
                "status": status,
                "current_year": current_year,
            },
        )
        params = {
            "from": "SACCO <notifications@wananchimali.com>",
            "to": [admin_email],
            "subject": f"Action Required: Loan Application - {status}",
            "html": email_body,
        }
        response = resend.Emails.send(params)
        logger.info(f"Admin notification email sent to {admin_email} with response: {response}")
        return response

    except Exception as e:
        logger.error(f"Error sending admin notification email: {str(e)}")
        return None

