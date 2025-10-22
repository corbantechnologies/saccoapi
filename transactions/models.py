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
        return (
            f"DownloadLog {self.file_name} by {self.admin.username} at {self.timestamp}"
        )
