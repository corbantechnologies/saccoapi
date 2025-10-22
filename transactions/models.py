from django.db import models
from django.contrib.auth import get_user_model

from accounts.abstracts import UniversalIdModel, TimeStampedModel, ReferenceModel

User = get_user_model()


class DownloadLog(UniversalIdModel, TimeStampedModel, ReferenceModel):
    admin = models.ForeignKey(User, on_delete=models.CASCADE)
    timestamp = models.DateTimeField(auto_now_add=True)
    file_name = models.CharField(max_length=100)
    cloudinary_url = models.URLField()

    def __str__(self):
        return f"DownloadLog {self.file_name} by {self.admin.member_no} at {self.timestamp}"


class BulkTransactionLog(UniversalIdModel, TimeStampedModel, ReferenceModel):
    admin = models.ForeignKey(User, on_delete=models.PROTECT)
    timestamp = models.DateTimeField(auto_now_add=True)
    file_name = models.CharField(max_length=100, blank=True, null=True)
    cloudinary_url = models.URLField(blank=True, null=True)
    transaction_type = models.CharField(max_length=50)  # e.g., "Savings Deposits"
    success_count = models.PositiveIntegerField(default=0)
    error_count = models.PositiveIntegerField(default=0)
    reference_prefix = models.CharField(max_length=50)

    def __str__(self):
        return f"{self.transaction_type} - {self.reference_prefix} - {self.timestamp}"
