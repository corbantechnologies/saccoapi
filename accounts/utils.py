import string
import secrets
import resend
import logging
from datetime import datetime

from django.core.mail import send_mail
from django.template.loader import render_to_string

from saccoapi.settings import DOMAIN

logger = logging.getLogger(__name__)


current_year = datetime.now().year


def generate_reference():
    characters = string.ascii_letters + string.digits
    random_string = "".join(secrets.choice(characters) for _ in range(12))
    return random_string.upper()


def generate_member_number():
    year = datetime.now().year % 100  # Last two digits of year
    random_number = "".join(secrets.choice(string.digits) for _ in range(6))
    return f"MBR{year}{random_number}"


def send_registration_confirmation_email(user):
    """
    Resend email integration
    """
    email_body = ""
    current_year = datetime.now().year

    try:
        email_body = render_to_string(
            "registration_confirmation.html",
            {"user": user, "current_year": current_year},
        )
        params = {
            "from": "Wekeza SACCO <onboarding@corbantechnologies.org>",
            "to": [user.email],
            "subject": "Registration Confirmation",
            "html": email_body,
        }
        response = resend.Emails.send(params)
        logger.info(f"Email sent to {user.email} with response: {response}")
        return response

    except Exception as e:
        logger.error(f"Error sending email to {user.email}: {str(e)}")
        return None


def send_member_number_email(user):
    """
    Resend email integration
    """
    email_body = ""
    current_year = datetime.now().year
    site_url = f"{DOMAIN}/login"

    try:
        email_body = render_to_string(
            "member_number.html",
            {"user": user, "current_year": current_year, "site_url": site_url},
        )
        params = {
            "from": "Wekeza SACCO <onboarding@corbantechnologies.org>",
            "to": [user.email],
            "subject": "Your Membership Number",
            "html": email_body,
        }
        response = resend.Emails.send(params)
        logger.info(f"Email sent to {user.email} with response: {response}")
        return response

    except Exception as e:
        logger.error(f"Error sending email to {user.email}: {str(e)}")
        return None


def send_account_creation_email(user):
    """
    A function to send a successful account creation email
    """
    email_body = ""
    current_year = datetime.now().year

    try:

        email_body = render_to_string(
            "account_created.html", {"user": user, "current_year": current_year}
        )
        params = {
            "from": "Wekeza SACCO <onboarding@corbantechnologies.org>",
            "to": [user.email],
            "subject": "Welcome to Wekeza SACCO",
            "html": email_body,
        }
        response = resend.Emails.send(params)
        logger.info(f"Email sent to {user.email} with response: {response}")
        return response

    except Exception as e:
        logger.error(f"Error sending email to {user.email}: {str(e)}")
        return None


def send_verification_email(user, verification_code):
    """
    A function to send a verification email
    """

    email_body = ""
    current_year = datetime.now().year

    try:
        email_body = render_to_string(
            "account_verification.html",
            {
                "user": user,
                "verification_code": verification_code,
                "current_year": current_year,
            },
        )
        params = {
            "from": "Wekeza SACCO <onboarding@corbantechnologies.org>",
            "to": [user.email],
            "subject": "Verify your account",
            "html": email_body,
        }
        response = resend.Emails.send(params)
        logger.info(f"Email sent to {user.email} with response: {response}")
        return response

    except Exception as e:
        logger.error(f"Error sending email to {user.email}: {str(e)}")
        return None


def send_password_reset_email(user, verification_code):
    """
    A function to send a password reset email
    """
    email_body = ""
    current_year = datetime.now().year

    try:
        email_body = render_to_string(
            "password_reset.html",
            {
                "user": user,
                "verification_code": verification_code,
                "current_year": current_year,
            },
        )
        params = {
            "from": "Wekeza SACCO <onboarding@corbantechnologies.org>",
            "to": [user.email],
            "subject": "Reset your password",
            "html": email_body,
        }
        response = resend.Emails.send(params)
        logger.info(f"Email sent to {user.email} with response: {response}")
        return response

    except Exception as e:
        logger.error(f"Error sending email to {user.email}: {str(e)}")
        return None
