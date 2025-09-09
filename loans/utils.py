import string
import secrets
from datetime import datetime


def generate_loan_account_number():
    """Generate a random 10-digit loan account number."""
    year = datetime.now().year % 100
    random_number = "".join(secrets.choice(string.digits) for _ in range(8))
    return f"LN{year}{random_number}"
