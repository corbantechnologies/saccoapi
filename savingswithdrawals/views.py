from rest_framework import generics
from rest_framework.permissions import IsAuthenticated

from savingswithdrawals.models import SavingsWithdrawal
from accounts.permissions import IsSystemAdminOrReadOnly
from savingswithdrawals.serializers import SavingsWithdrawalSerializer
from savingswithdrawals.utils import (
    send_withdrawal_request_email,
    send_withdrawal_status_email,
)


class SavingsWithdrawalListCreateView(generics.ListCreateAPIView):
    queryset = SavingsWithdrawal.objects.all()
    serializer_class = SavingsWithdrawalSerializer
    permission_classes = [
        IsAuthenticated,
    ]

    def perform_create(self, serializer):
        withdrawal = serializer.save(withdrawn_by=self.request.user)
        # Send email if user has an email address
        if self.request.user.email:
            send_withdrawal_request_email(self.request.user, withdrawal)


class SavingsWithdrawalDetailView(generics.RetrieveAPIView):
    queryset = SavingsWithdrawal.objects.all()
    serializer_class = SavingsWithdrawalSerializer
    lookup_field = "reference"
    permission_classes = [
        IsAuthenticated,
    ]


# SACCO Admin approves savings withdrawals


class SavingsWithdrawalUpdateView(generics.RetrieveUpdateAPIView):
    queryset = SavingsWithdrawal.objects.all()
    serializer_class = SavingsWithdrawalSerializer
    lookup_field = "identity"
    permission_classes = [
        IsSystemAdminOrReadOnly,
    ]

    def perform_update(self, serializer):
        withdrawal = serializer.save()
        # Send email if user has an email address and transaction status has changed
        if (
            withdrawal.withdrawn_by.email
            and "transaction_status" in serializer.validated_data
        ):
            send_withdrawal_status_email(withdrawal.withdrawn_by, withdrawal)
