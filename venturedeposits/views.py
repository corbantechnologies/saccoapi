from rest_framework import generics

from accounts.permissions import IsSystemAdminOrReadOnly
from venturedeposits.models import VentureDeposit
from venturedeposits.serializers import VentureDepositSerializer
from venturedeposits.utils import send_venture_deposit_made_email


class VentureDepositListCreateView(generics.ListCreateAPIView):
    queryset = VentureDeposit.objects.all()
    serializer_class = VentureDepositSerializer
    permission_classes = [
        IsSystemAdminOrReadOnly,
    ]

    def perform_create(self, serializer):
        deposit = serializer.save(deposited_by=self.request.user)
        # Send email to the account owner if they have an email address
        account_owner = deposit.venture_account.member
        if account_owner.email:
            send_venture_deposit_made_email(account_owner, deposit)


class VentureDepositDetailView(generics.RetrieveAPIView):
    queryset = VentureDeposit.objects.all()
    serializer_class = VentureDepositSerializer
    permission_classes = [
        IsSystemAdminOrReadOnly,
    ]
    lookup_field = "reference"
