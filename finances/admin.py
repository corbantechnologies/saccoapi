from django.contrib import admin
from .models import GLAccount, JournalEntry, Journal, TransactionTemplate, TransactionTemplateLine

@admin.register(GLAccount)
class GLAccountAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'account_type', 'parent', 'is_active')
    list_filter = ('account_type', 'is_active')
    search_fields = ('code', 'name')

class TransactionTemplateLineInline(admin.TabularInline):
    model = TransactionTemplateLine
    extra = 2

@admin.register(TransactionTemplate)
class TransactionTemplateAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'is_active')
    search_fields = ('code', 'name')
    inlines = [TransactionTemplateLineInline]

class JournalEntryInline(admin.TabularInline):
    model = JournalEntry
    extra = 0
    readonly_fields = ('transaction_date', 'description', 'reference_id', 'source_model', 'posted_by')

@admin.register(Journal)
class JournalAdmin(admin.ModelAdmin):
    list_display = ('id', 'transaction_date', 'description', 'template', 'source_model')
    list_filter = ('transaction_date', 'source_model')
    search_fields = ('description', 'reference_id')
    inlines = [JournalEntryInline]

@admin.register(JournalEntry)
class JournalEntryAdmin(admin.ModelAdmin):
    list_display = ('transaction_date', 'gl_account', 'debit', 'credit', 'source_model')
    list_filter = ('transaction_date', 'gl_account')
    search_fields = ('description', 'reference_id')
    raw_id_fields = ('gl_account', 'posted_by')
