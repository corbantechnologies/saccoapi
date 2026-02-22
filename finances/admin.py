from django.contrib import admin
from .models import GLAccount, JournalEntry

@admin.register(GLAccount)
class GLAccountAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'account_type', 'is_active')
    list_filter = ('account_type', 'is_active')
    search_fields = ('code', 'name')
    ordering = ('code',)

@admin.register(JournalEntry)
class JournalEntryAdmin(admin.ModelAdmin):
    list_display = ('transaction_date', 'gl_account', 'debit', 'credit', 'description')
    list_filter = ('transaction_date', 'gl_account__account_type')
    search_fields = ('description', 'reference_id', 'gl_account__name')
    date_hierarchy = 'transaction_date'
    raw_id_fields = ('gl_account', 'posted_by')
