from rest_framework import generics

from savingstypes.models import SavingsType
from savingstypes.serializers import SavingsTypeSerializer
from accounts.permissions import IsSystemAdminOrReadOnly


class SavingsTypeListCreateView(generics.ListCreateAPIView):
    queryset = SavingsType.objects.all()
    serializer_class = SavingsTypeSerializer
    permission_classes = [
        IsSystemAdminOrReadOnly,
    ]


class SavingsTypeDetailView(generics.RetrieveUpdateAPIView):
    queryset = SavingsType.objects.all()
    serializer_class = SavingsTypeSerializer
    permission_classes = [
        IsSystemAdminOrReadOnly,
    ]
    lookup_field = "reference"
