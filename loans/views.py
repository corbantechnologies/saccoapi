from rest_framework import generics
from rest_framework.permissions import IsAuthenticated

from loans.models import LoanAccount
from loans.serializers import LoanAccountSerializer
from accounts.permissions import IsSystemAdminOrReadOnly


# Members can view and create their own loan accounts
class LoanAccountListCreateView(generics.ListCreateAPIView):
    queryset = LoanAccount.objects.all()
    serializer_class = LoanAccountSerializer
    permission_classes = [
        IsAuthenticated,
    ]

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    def get_queryset(self):
        return self.queryset.filter(user=self.request.user).prefetch_related(
            "repayments", "loan_disbursements", "loan_interests"
        )


class LoanAccountDetailView(generics.RetrieveAPIView):
    queryset = LoanAccount.objects.all()
    serializer_class = LoanAccountSerializer
    permission_classes = [
        IsAuthenticated,
    ]
    lookup_field = "identity"

    def get_queryset(self):
        return self.queryset.filter(user=self.request.user).prefetch_related(
            "repayments", "loan_disbursements", "loan_interests"
        )
