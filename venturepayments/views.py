from rest_framework import generics

from venturepayments.models import VenturePayment
from accounts.permissions import IsSystemAdminOrReadOnly
from venturepayments.serializers import VenturePaymentSerializer
from venturepayments.utils import (
    send_venture_payment_confirmation_email,
)


# TODO: Sacco Admins make the payments for now
class VenturePaymentListCreateView(generics.ListCreateAPIView):
    queryset = VenturePayment.objects.all()
    serializer_class = VenturePaymentSerializer
    permission_classes = [
        IsSystemAdminOrReadOnly,
    ]

    def perform_create(self, serializer):
        payment = serializer.save(paid_by=self.request.user)
        # Send email to the account owner if they have an email address
        account_owner = payment.venture_account.member
        if account_owner.email:
            send_venture_payment_confirmation_email(account_owner, payment)


class VenturePaymentDetailView(generics.RetrieveAPIView):
    queryset = VenturePayment.objects.all()
    serializer_class = VenturePaymentSerializer
    permission_classes = [
        IsSystemAdminOrReadOnly,
    ]
    lookup_field = "reference"
