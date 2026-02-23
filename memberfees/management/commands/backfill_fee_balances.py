from django.core.management.base import BaseCommand
from django.db.models import Sum
from django.db import transaction
from memberfees.models import MemberFee
from decimal import Decimal

class Command(BaseCommand):
    help = 'Backfill remaining_balance for existing MemberFee records'

    def handle(self, *args, **options):
        self.stdout.write("Starting backfill of MemberFee balances...")
        
        fees = MemberFee.objects.all()
        count = fees.count()
        updated = 0

        with transaction.atomic():
            for fee in fees:
                total_paid = fee.payments.aggregate(total=Sum('amount'))['total'] or Decimal('0')
                fee.remaining_balance = max(fee.amount - total_paid, Decimal('0'))
                
                # Also ensure is_paid is consistent
                if total_paid >= fee.amount:
                    fee.is_paid = True
                else:
                    fee.is_paid = False
                
                fee.save()
                updated += 1
                if updated % 100 == 0:
                    self.stdout.write(f"Processed {updated}/{count} fees...")

        self.stdout.write(self.style.SUCCESS(f"Successfully updated {updated} MemberFee records."))
