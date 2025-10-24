from rest_framework import generics, status
from rest_framework.response import Response
from loanintereststamarind.models import TamarindLoanInterest
from loanintereststamarind.serializers import TamarindLoanInterestSerializer

from accounts.permissions import IsSystemAdminOrReadOnly

class TamarindLoanInterestListCreateView(generics.ListCreateAPIView):
    queryset = TamarindLoanInterest.objects.all()
    serializer_class = TamarindLoanInterestSerializer
    permission_classes = (IsSystemAdminOrReadOnly,)

    def perform_create(self, serializer):
        serializer.save(entered_by=self.request.user)


class TamarindLoanInterestDetailView(generics.RetrieveAPIView):
    queryset = TamarindLoanInterest.objects.all()
    serializer_class = TamarindLoanInterestSerializer
    permission_classes = (IsSystemAdminOrReadOnly,)
    lookup_field = "reference"
