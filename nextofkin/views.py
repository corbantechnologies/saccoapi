from rest_framework import generics
from rest_framework.permissions import IsAuthenticated

from nextofkin.models import NextOfKin
from nextofkin.serializers import NextOfKinSerializer


class NextOfKinListCreateView(generics.ListCreateAPIView):
    queryset = NextOfKin.objects.all()
    serializer_class = NextOfKinSerializer
    permission_classes = [
        IsAuthenticated,
    ]

    def perform_create(self, serializer):
        serializer.save(member=self.request.user)

    def get_queryset(self):
        return self.queryset.filter(member=self.request.user)


class NextOfKinDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = NextOfKin.objects.all()
    serializer_class = NextOfKinSerializer
    permission_classes = [
        IsAuthenticated,
    ]
    lookup_field = "reference"

    def get_queryset(self):
        return self.queryset.filter(member=self.request.user)
