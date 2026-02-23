from django.db import models
from django.contrib.auth import get_user_model
from accounts.abstracts import UniversalIdModel, TimeStampedModel

User = get_user_model()

class GLAccount(UniversalIdModel, TimeStampedModel):
    ACCOUNT_TYPES = (
        ('Asset', 'Asset'),
        ('Liability', 'Liability'),
        ('Equity', 'Equity'),
        ('Revenue', 'Revenue'),
        ('Expense', 'Expense'),
    )

    code = models.CharField(max_length=20, unique=True, help_text="e.g. 1000, 2010")
    name = models.CharField(max_length=100, unique=True)
    account_type = models.CharField(max_length=20, choices=ACCOUNT_TYPES)
    description = models.TextField(blank=True, null=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['code']
        verbose_name = "GL Account"
        verbose_name_plural = "GL Accounts"

    def __str__(self):
        return f"{self.code} - {self.name}"

class JournalEntry(UniversalIdModel, TimeStampedModel):
    transaction_date = models.DateField()
    description = models.CharField(max_length=255)
    
    # Simple double entry: record each line as a single entry
    gl_account = models.ForeignKey(GLAccount, on_delete=models.PROTECT, related_name='journal_entries')
    debit = models.DecimalField(max_digits=20, decimal_places=2, default=0)
    credit = models.DecimalField(max_digits=20, decimal_places=2, default=0)
    
    # Source tracking
    reference_id = models.CharField(max_length=255, blank=True, null=True, help_text="ID of the original transaction record")
    source_model = models.CharField(max_length=100, blank=True, null=True, help_text="e.g. SavingsDeposit")
    
    posted_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        verbose_name = "Journal Entry"
        verbose_name_plural = "Journal Entries"
        ordering = ['-transaction_date', '-created_at']

    def __str__(self):
        return f"{self.transaction_date} - {self.gl_account.name} ({'DR' if self.debit > 0 else 'CR'})"
