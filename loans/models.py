# from django.db import models
# from django.contrib.auth import get_user_model
# from django.utils.text import slugify

# from accounts.abstracts import TimeStampedModel, UniversalIdModel, ReferenceModel
# from loantypes.models import LoanType
# from loans.utils import generate_loan_account_number

# User = get_user_model()

# class LoanAccount(TimeStampedModel, UniversalIdModel, ReferenceModel):
#     user = models.ForeignKey(
#         User, on_delete=models.CASCADE, related_name="loan_accounts"
#     )
#     loan_type = models.ForeignKey(
#         LoanType, on_delete=models.PROTECT, related_name="loan_accounts"
#     )
#     account_number = models.CharField(
#         max_length=20, unique=True, default=generate_loan_account_number
#     )
#     loan_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
#     balance = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
#     is_active = models.BooleanField(default=True)
#     identity = models.CharField(max_length=100, blank=True, null=True, unique=True)

#     class Meta:
#         verbose_name = "Loan Account"
#         verbose_name_plural = "Loan Accounts"
#         ordering = ["-created_at"]

#     def __str__(self):
#         return f"{self.account_number} - {self.user.get_full_name()}"
    
#     def save(self, *args, **kwargs):
#         if not self.identity:
#             self.identity = slugify(f"{self.user.member_no}-{self.account_number}")
#         super().save(*args, **kwargs)