import logging
from rest_framework import generics
from django.contrib.auth import get_user_model

from savingstypes.models import SavingsType
from savingstypes.serializers import SavingsTypeSerializer
from accounts.permissions import IsSystemAdminOrReadOnly
from savings.models import SavingsAccount

logger = logging.getLogger(__name__)

User = get_user_model()


class SavingsTypeListCreateView(generics.ListCreateAPIView):
    queryset = SavingsType.objects.all()
    serializer_class = SavingsTypeSerializer
    permission_classes = [
        IsSystemAdminOrReadOnly,
    ]

    def perform_create(self, serializer):
        savings_type = serializer.save()

        members = User.objects.filter(is_member=True)
        created_accounts = []
        for member in members:
            # Check if the member already has an account of this type
            if not SavingsAccount.objects.filter(
                member=member, account_type=savings_type
            ).exists():
                account = SavingsAccount.objects.create(
                    member=member, account_type=savings_type, is_active=True
                )
                created_accounts.append(str(account))
        logger.info(
            f"Created {len(created_accounts)} SavingsAccounts: {', '.join(created_accounts)}"
        )


class SavingsTypeDetailView(generics.RetrieveUpdateAPIView):
    queryset = SavingsType.objects.all()
    serializer_class = SavingsTypeSerializer
    permission_classes = [
        IsSystemAdminOrReadOnly,
    ]
    lookup_field = "reference"
