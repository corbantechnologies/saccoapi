import logging
from rest_framework import generics
from django.contrib.auth import get_user_model

from accounts.permissions import IsSystemAdminOrReadOnly
from loantypes.models import LoanType
from loantypes.serializers import LoanTypeSerializer
from loans.models import LoanAccount

logger = logging.getLogger(__name__)

User = get_user_model()


class LoanTypeListCreateView(generics.ListCreateAPIView):
    queryset = LoanType.objects.all()
    serializer_class = LoanTypeSerializer
    permission_classes = [
        IsSystemAdminOrReadOnly,
    ]

    def perform_create(self, serializer):
        loan_type = serializer.save()

        members = User.objects.filter(is_member=True)
        created_accounts = []

        for member in members:
            # Check if the members already has an account of this type
            if not LoanAccount.objects.filter(
                member=member, loan_type=loan_type
            ).exists():
                account = LoanAccount.objects.create(
                    member=member, loan_type=loan_type, is_active=True
                )
                created_accounts.append(str(account))
        logger.info(
            f"Created {len(created_accounts)} LoanAccounts: {', '.join(created_accounts)}"
        )


class LoanTypeDetailView(generics.RetrieveUpdateAPIView):
    queryset = LoanType.objects.all()
    serializer_class = LoanTypeSerializer
    permission_classes = [
        IsSystemAdminOrReadOnly,
    ]
    lookup_field = "reference"
