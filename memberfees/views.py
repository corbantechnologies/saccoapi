from rest_framework import generics
from rest_framework.permissions import IsAuthenticated

from memberfees.models import MemberFee
from memberfees.serializers import MemberFeeSerializer


class MemberFeeListView(generics.ListAPIView):
    queryset = MemberFee.objects.all()
    serializer_class = MemberFeeSerializer
    permission_classes = [
        IsAuthenticated,
    ]


class MemberFeeRetrieveView(generics.RetrieveAPIView):
    queryset = MemberFee.objects.all()
    serializer_class = MemberFeeSerializer
    permission_classes = [
        IsAuthenticated,
    ]
    lookup_field = "reference"

