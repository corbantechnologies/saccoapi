from django.db import models
from django.contrib.auth import get_user_model

from accounts.abstracts import TimeStampedModel, UniversalIdModel, ReferenceModel

User = get_user_model()


"""
Finance section
- A member can have multiple savings accounts of different types: savings, holiday savings, emergency savings
- A member can have multiple loan accounts of different types: development loan, school fee loan, emergency loan
"""

