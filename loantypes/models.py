from django.db import models

from accounts.abstracts import TimeStampedModel, UniversalIdModel, ReferenceModel


class LoanType(TimeStampedModel, UniversalIdModel, ReferenceModel):
    name = models.CharField(max_length=2550, unique=True)
    description = models.TextField()

    def __str__(self):
        return self.name
