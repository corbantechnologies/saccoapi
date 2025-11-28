# guaranteerequests/views.py
from rest_framework import generics, status, serializers
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.db import transaction
from django.db.models import Q, F
from decimal import Decimal


from .models import GuaranteeRequest
from .serializers import (
    GuaranteeRequestSerializer,
    GuaranteeApprovalDeclineSerializer,
)
from loanapplications.utils import compute_loan_coverage
from guaranteerequests.utils import send_guarantee_request_status_email


class GuaranteeRequestListCreateView(generics.ListCreateAPIView):
    """
    POST  → Member creates guarantee request
    GET   → Member & guarantor see their requests
    """

    queryset = GuaranteeRequest.objects.all()
    permission_classes = [IsAuthenticated]
    serializer_class = GuaranteeRequestSerializer

    def perform_create(self, serializer):
        serializer.save(member=self.request.user)

    def get_queryset(self):
        user = self.request.user
        return (
            super()
            .get_queryset()
            .filter(Q(member=user) | Q(guarantor__member=user))
            .select_related(
                "member",
                "guarantor__member",
                "loan_application",
                "loan_application__product",
            )
            .prefetch_related("loan_application__guarantors")
        )


class GuaranteeRequestRetrieveView(generics.RetrieveAPIView):
    """
    GET /guaranteerequests/<reference>/
    Only member or guarantor
    """

    serializer_class = GuaranteeRequestSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = "reference"

    def get_queryset(self):
        user = self.request.user
        return GuaranteeRequest.objects.filter(
            Q(member=user) | Q(guarantor__member=user)
        ).select_related("member", "guarantor__member", "loan_application")


class GuaranteeRequestUpdateStatusView(generics.UpdateAPIView):
    """
    PATCH /guaranteerequests/<reference>/status/
    Only guarantor can Accept or Decline
    """

    serializer_class = GuaranteeApprovalDeclineSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = "reference"

    def get_queryset(self):
        return GuaranteeRequest.objects.filter(guarantor__member=self.request.user)

    @transaction.atomic
    def perform_update(self, serializer):
        instance = self.get_object()
        new_status = serializer.validated_data["status"]
        old_status = instance.status

        # 1. Check if update is allowed
        allowed_statuses = ["Pending", "Accepted"]
        if old_status not in allowed_statuses:
            raise serializers.ValidationError(
                {"status": f"Cannot update request in '{old_status}' state."}
            )

        # 2. Loan not finalized
        loan_app = instance.loan_application
        FINAL_STATES = ["Submitted", "Approved", "Disbursed", "Declined", "Cancelled"]
        if loan_app.status in FINAL_STATES:
            raise serializers.ValidationError(
                {"status": f"Loan application is in '{loan_app.status}' state."}
            )

        # 3. Update status
        instance.status = new_status
        
        # Allow updating amount if provided in serializer (and if accepting)
        if new_status == "Accepted":
             new_amount = serializer.validated_data.get("guaranteed_amount")
             if new_amount:
                 instance.guaranteed_amount = new_amount

        instance.save(update_fields=["status", "guaranteed_amount"])

        profile = instance.guarantor
        amount = instance.guaranteed_amount

        # 4. ACCEPT
        if new_status == "Accepted":
            # NO COMMITMENT HERE ANYMORE. DEFERRED TO SUBMISSION.
            
            # Self-guarantee: update loan
            if instance.guarantor.member == loan_app.member:
                loan_app.self_guaranteed_amount = amount
                loan_app.save(update_fields=["self_guaranteed_amount"])

            # Auto-update loan status
            coverage = compute_loan_coverage(loan_app)
            if coverage["is_fully_covered"]:
                loan_app.status = "Ready for Submission"
                loan_app.save(update_fields=["status"])

        # 5. DECLINE (only if previously Accepted)
        elif new_status == "Declined" and old_status == "Accepted":
            # NO REVERT NEEDED IF NOT COMMITTED.
            # But if it WAS committed (legacy or already submitted?), we might need to check.
            # Assuming we are in pre-submission phase, no commitment has happened.
            
            if instance.guarantor.member == loan_app.member:
                loan_app.self_guaranteed_amount = Decimal("0")
                loan_app.save(update_fields=["self_guaranteed_amount"])

        if instance.member.email:
            send_guarantee_request_status_email(instance)

        return Response(status=status.HTTP_200_OK, data=serializer.data)
