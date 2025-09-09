from rest_framework import generics

from accounts.permissions import IsSystemAdminOrReadOnly
from loantypes.models import LoanType
from loantypes.serializers import LoanTypeSerializer


class LoanTypeListCreateView(generics.ListCreateAPIView):
    queryset = LoanType.objects.all()
    serializer_class = LoanTypeSerializer
    permission_classes = [
        IsSystemAdminOrReadOnly,
    ]


class LoanTypeDetailView(generics.RetrieveUpdateAPIView):
    queryset = LoanType.objects.all()
    serializer_class = LoanTypeSerializer
    permission_classes = [
        IsSystemAdminOrReadOnly,
    ]
    lookup_field = "reference"
