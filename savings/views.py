from rest_framework import generics
from rest_framework.permissions import IsAuthenticated

from savings.models import SavingsAccount
from savings.serializers import SavingsAccountSerializer


class SavingsAccountListCreateView(generics.ListCreateAPIView):
    queryset = SavingsAccount.objects.all()
    serializer_class = SavingsAccountSerializer
    permission_classes = [
        IsAuthenticated,
    ]

    def get_queryset(self):
        return self.queryset.filter(user=self.request.user)


class SavingsAccountDetailView(generics.RetrieveAPIView):
    queryset = SavingsAccount.objects.all()
    serializer_class = SavingsAccountSerializer
    permission_classes = [
        IsAuthenticated,
    ]
    lookup_field = "identity"

    def get_queryset(self):
        return self.queryset.filter(user=self.request.user)
