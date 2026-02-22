import logging
from rest_framework import generics
from django.contrib.auth import get_user_model

from feetypes.models import FeeType
from feetypes.serializers import FeeTypeSerializer
from accounts.permissions import IsSystemAdminOrReadOnly
from memberfees.models import MemberFee

User = get_user_model()

logger = logging.getLogger(__name__)


class FeeTypeListCreateView(generics.ListCreateAPIView):
    queryset = FeeType.objects.all()
    serializer_class = FeeTypeSerializer
    permission_classes = [
        IsSystemAdminOrReadOnly,
    ]

    def perform_create(self, serializer):
        fee_type = serializer.save()

        members = User.objects.filter(is_member=True)
        created_accounts = []
        for member in members:
            # Check if the member already has an account of this type
            if not MemberFee.objects.filter(
                member=member, fee_type=fee_type
            ).exists():
                account = MemberFee.objects.create(
                    member=member, fee_type=fee_type,
                )
                created_accounts.append(str(account))
        logger.info(
            f"Created {len(created_accounts)} MemberFees: {', '.join(created_accounts)}"
        )


class FeeTypeDetailView(generics.RetrieveUpdateAPIView):
    queryset = FeeType.objects.all()
    serializer_class = FeeTypeSerializer
    permission_classes = [
        IsSystemAdminOrReadOnly,
    ]
    lookup_field = "reference"
