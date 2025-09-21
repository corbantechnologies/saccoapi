from rest_framework import generics

from accounts.permissions import IsSystemAdminOrReadOnly
from savingsdeposits.models import SavingsDeposit
from savingsdeposits.serializers import SavingsDepositSerializer


class SavingsDepositListCreateView(generics.ListCreateAPIView):
    queryset = SavingsDeposit.objects.all()
    serializer_class = SavingsDepositSerializer
    permission_classes = [
        IsSystemAdminOrReadOnly,
    ]

    def perform_create(self, serializer):
        serializer.save(deposited_by=self.request.user)


class SavingsDepositView(generics.RetrieveAPIView):
    queryset = SavingsDeposit.objects.all()
    serializer_class = SavingsDepositSerializer
    permission_classes = [
        IsSystemAdminOrReadOnly,
    ]
    lookup_field = "reference"
