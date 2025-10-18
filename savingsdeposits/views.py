from rest_framework import generics
from accounts.permissions import IsSystemAdminOrReadOnly
from savingsdeposits.models import SavingsDeposit
from savingsdeposits.serializers import SavingsDepositSerializer
from savingsdeposits.utils import send_deposit_made_email


class SavingsDepositListCreateView(generics.ListCreateAPIView):
    queryset = SavingsDeposit.objects.all()
    serializer_class = SavingsDepositSerializer
    permission_classes = [IsSystemAdminOrReadOnly]

    def perform_create(self, serializer):
        deposit = serializer.save(deposited_by=self.request.user)
        # Send email to the account owner if they have an email address
        account_owner = deposit.savings_account.member
        if account_owner.email:
            send_deposit_made_email(account_owner, deposit)


class SavingsDepositView(generics.RetrieveAPIView):
    queryset = SavingsDeposit.objects.all()
    serializer_class = SavingsDepositSerializer
    permission_classes = [IsSystemAdminOrReadOnly]
    lookup_field = "reference"
