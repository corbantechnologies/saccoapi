from django.db import models
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
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
    parent = models.ForeignKey(
        'self', on_delete=models.CASCADE, related_name='sub_accounts',
        null=True, blank=True, help_text="Optional parent account for hierarchical grouping"
    )
    description = models.TextField(blank=True, null=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['code']
        verbose_name = "GL Account"
        verbose_name_plural = "GL Accounts"

    def __str__(self):
        indent = '--' if self.parent else ''
        return f"{indent}{self.code} - {self.name}"

    def clean(self):
        if self.parent and self.parent.account_type != self.account_type:
            raise ValidationError("Sub-accounts must have the same account type as their parent.")
        if self.parent == self:
            raise ValidationError("An account cannot be its own parent.")

class TransactionTemplate(UniversalIdModel, TimeStampedModel):
    """
    Configurable rules for posting transactions. Replaces hardcoded mappings.
    """
    code = models.CharField(max_length=50, unique=True, help_text="e.g., 'savings_deposit'")
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True, null=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.name} ({self.code})"

class TransactionTemplateLine(UniversalIdModel, TimeStampedModel):
    transaction_template = models.ForeignKey(TransactionTemplate, on_delete=models.CASCADE, related_name='lines')
    gl_account = models.ForeignKey(GLAccount, on_delete=models.PROTECT, related_name='template_lines')
    is_debit = models.BooleanField(default=True, help_text="True for Debit, False for Credit")

    def __str__(self):
        action = "DR" if self.is_debit else "CR"
        return f"{self.transaction_template.name} - {action} {self.gl_account.name}"

class Journal(UniversalIdModel, TimeStampedModel):
    """
    Represents the header for a compound journal entry.
    """
    transaction_date = models.DateField()
    description = models.CharField(max_length=255)
    reference_id = models.CharField(max_length=255, blank=True, null=True)
    source_model = models.CharField(max_length=100, blank=True, null=True)
    template = models.ForeignKey(TransactionTemplate, null=True, blank=True, on_delete=models.SET_NULL)
    posted_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        verbose_name = "Journal"
        verbose_name_plural = "Journals"
        ordering = ['-transaction_date', '-created_at']

    def __str__(self):
        return f"JRNL {self.id} on {self.transaction_date}"

class JournalEntry(UniversalIdModel, TimeStampedModel):
    journal = models.ForeignKey(Journal, on_delete=models.CASCADE, related_name='entries', null=True, blank=True)
    
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
