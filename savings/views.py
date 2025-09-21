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

    def perform_create(self, serializer):
        serializer.save(member=self.request.user)

    def get_queryset(self):
        return self.queryset.filter(member=self.request.user).prefetch_related(
            "deposits"
        )


class SavingsAccountDetailView(generics.RetrieveAPIView):
    queryset = SavingsAccount.objects.all()
    serializer_class = SavingsAccountSerializer
    permission_classes = [
        IsAuthenticated,
    ]
    lookup_field = "identity"

    def get_queryset(self):
        return self.queryset.filter(member=self.request.user).prefetch_related(
            "deposits"
        )
