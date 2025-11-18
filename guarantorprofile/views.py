from rest_framework import generics

from accounts.permissions import IsSystemAdminOrReadOnly
from guarantorprofile.models import GuarantorProfile
from guarantorprofile.serializers import GuarantorProfileSerializer


class GuarantorProfileListCreateView(generics.ListCreateAPIView):
    queryset = GuarantorProfile.objects.all()
    serializer_class = GuarantorProfileSerializer
    permission_classes = [IsSystemAdminOrReadOnly]


class GuarantorProfileDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = GuarantorProfile.objects.all()
    serializer_class = GuarantorProfileSerializer
    permission_classes = [IsSystemAdminOrReadOnly]
    lookup_field = "member__member_no"
