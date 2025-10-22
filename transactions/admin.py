from django.contrib import admin

from transactions.models import DownloadLog, BulkTransactionLog

admin.site.register(DownloadLog)
admin.site.register(BulkTransactionLog)
