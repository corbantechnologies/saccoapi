import string
import secrets
from datetime import datetime


def generate_account_number():
    """Generate a random 10-digit account number."""
    year = datetime.now().year % 100
    random_number = "".join(secrets.choice(string.digits) for _ in range(10))
    return f"WM{year}{random_number}"


print(generate_account_number())
