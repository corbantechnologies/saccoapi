from rest_framework import generics

from accounts.permissions import IsSystemAdminOrReadOnly
from loanrepayments.models import LoanRepayment
from loanrepayments.serializers import LoanRepaymentSerializer


class LoanRepaymentListCreateView(generics.ListCreateAPIView):
    queryset = LoanRepayment.objects.all()
    serializer_class = LoanRepaymentSerializer
    permission_classes = [
        IsSystemAdminOrReadOnly,
    ]

    def perform_create(self, serializer):
        serializer.save(paid_by=self.request.user)


class LoanRepaymentDetailView(generics.RetrieveAPIView):
    queryset = LoanRepayment.objects.all()
    serializer_class = LoanRepaymentSerializer
    permission_classes = [
        IsSystemAdminOrReadOnly,
    ]
    lookup_field = "reference"
