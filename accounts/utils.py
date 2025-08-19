import string
import secrets
from datetime import datetime

from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.template.loader import render_to_string

from saccoapi.settings import EMAIL_USER


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
    subject = "Registration Confirmation"
    email_body = render_to_string("registration_confirmation.html", {"user": user})
    send_mail(
        subject=subject,
        message="",
        from_email=EMAIL_USER,
        recipient_list=[user.email],
        fail_silently=False,
        html_message=email_body,
    )


def send_member_number_email(user):
    subject = "Your Membership Number"
    email_body = render_to_string(
        "member_number.html", {"user": user, "member_no": user.member_no}
    )
    send_mail(
        subject=subject,
        message="",
        from_email=EMAIL_USER,
        recipient_list=[user.email],
        fail_silently=False,
        html_message=email_body,
    )


def send_account_creation_email(user):
    """
    A function to send a successful account creation email
    """
    current_year = datetime.now().year
    email_body = render_to_string(
        "account_created.html",
        {
            "user": user,
            "current_year": current_year,
            "member_no": user.member_no,
        },
    )

    send_mail(
        subject="Welcome to Wekeza SACCO",
        message="",  # Leave plain text empty if you're only sending HTML
        from_email=EMAIL_USER,
        recipient_list=[user.email],
        fail_silently=False,
        html_message=email_body,  # Provide the rendered HTML template here
    )


def send_verification_email(user, verification_code):
    """
    A function to send a verification email
    """
    current_year = datetime.now().year
    email_body = render_to_string(
        "account_verification.html",
        {
            "user": user,
            "verification_code": verification_code,
            "current_year": current_year,
        },
    )

    send_mail(
        subject="Verify your account",
        message="",  # Leave plain text empty if you're only sending HTML
        from_email=EMAIL_USER,
        recipient_list=[user.email],
        fail_silently=False,
        html_message=email_body,  # Provide the rendered HTML template here
    )


def send_password_reset_email(user, verification_code):
    """
    A function to send a password reset email
    """
    current_year = datetime.now().year
    email_body = render_to_string(
        "password_reset.html",
        {
            "user": user,
            "verification_code": verification_code,
            "current_year": current_year,
        },
    )

    send_mail(
        subject="Reset your password",
        message="",  # Leave plain text empty if you're only sending HTML
        from_email=EMAIL_USER,
        recipient_list=[user.email],
        fail_silently=False,
        html_message=email_body,  # Provide the rendered HTML template here
    )
