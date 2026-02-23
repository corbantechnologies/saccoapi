from django.core.management.base import BaseCommand
from finances.models import GLAccount

class Command(BaseCommand):
    help = "Initialize required GL accounts for the SACCO system"

    def handle(self, *args, **options):
        required_accounts = [
            {
                "code": "2030",
                "name": "Member Contributions",
                "account_type": "Liability"
            }
            # Add other accounts here if needed in the future
        ]

        for acc_data in required_accounts:
            acc, created = GLAccount.objects.get_or_create(
                code=acc_data["code"],
                defaults={
                    "name": acc_data["name"],
                    "account_type": acc_data["account_type"]
                }
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f"Created account: {acc.code} - {acc.name}"))
            else:
                # If it exists but name/type differs, we might want to update or just log
                if acc.name != acc_data["name"] or acc.account_type != acc_data["account_type"]:
                    self.stdout.write(self.style.WARNING(f"Account {acc.code} already exists but with different details."))
                else:
                    self.stdout.write(f"Account {acc.code} already exists.")

        self.stdout.write(self.style.SUCCESS("GL Setup complete."))
