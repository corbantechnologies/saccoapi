import string
import secrets
from datetime import datetime


def generate_venture_account_number():
    year = datetime.now().year % 100
    random_number = "".join(secrets.choice(string.digits) for _ in range(8))
    return f"VN{year}{random_number}"
