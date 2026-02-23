import string
import secrets
from datetime import datetime


def generate_fee_account_number():
    """Generate a random 10-digit account number."""
    year = datetime.now().year % 100
    random_number = "".join(secrets.choice(string.digits) for _ in range(8))
    return f"{year}{random_number}"


