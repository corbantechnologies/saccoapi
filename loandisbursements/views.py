import csv
import io
import cloudinary.uploader
import logging
from datetime import date
from django.db import transaction
from decimal import Decimal
from rest_framework.response import Response
from accounts.permissions import IsSystemAdminOrReadOnly
from rest_framework import generics, status

from transactions.models import BulkTransactionLog
from loandisbursements.models import LoanDisbursement
from loandisbursements.serializers import (
    LoanDisbursementSerializer,
    BulkLoanDisbursementSerializer,
)

logger = logging.getLogger(__name__)


class LoanDisbursementListCreateView(generics.ListCreateAPIView):
    queryset = LoanDisbursement.objects.all()
    serializer_class = LoanDisbursementSerializer
    permission_classes = [IsSystemAdminOrReadOnly]

    def perform_create(self, serializer):
        disbursement = serializer.save(disbursed_by=self.request.user)
        # Send email to the account owner if they have an email address
        # account_owner = disbursement.loan_account.member
        # if account_owner.email:
        #     send_disbursement_made_email(account_owner, disbursement)


class LoanDisbursementDetailView(generics.RetrieveAPIView):
    queryset = LoanDisbursement.objects.all()
    serializer_class = LoanDisbursementSerializer
    lookup_field = "reference"


"""
Bulk Transaction
"""


class BulkLoanDisbursementView(generics.CreateAPIView):
    permission_classes = [IsSystemAdminOrReadOnly]
    serializer_class = BulkLoanDisbursementSerializer

    def perform_create(self, serializer):
        disbursements_data = serializer.validated_data.get("disbursements", [])
        admin = self.request.user
        today = date.today()
        date_str = today.strftime("%Y%m%d")
        prefix = f"LOAN-BULK-{date_str}"

        # Initialize log
        log = BulkTransactionLog.objects.create(
            admin=admin,
            transaction_type="Loan Disbursements",
            reference_prefix=prefix,
            success_count=0,
            error_count=0,
        )

        success_count = 0
        error_count = 0
        errors = []

        with transaction.atomic():
            for index, disbursement_data in enumerate(disbursements_data, 1):
                try:
                    # Add disbursed_by and reference
                    disbursement_data["disbursed_by"] = admin
                    disbursement_data["reference"] = f"{prefix}-{index:04d}"
                    disbursement_data["transaction_status"] = disbursement_data.get(
                        "transaction_status", "Completed"
                    )
                    disbursement_data["is_active"] = disbursement_data.get(
                        "is_active", True
                    )
                    disbursement_data["created_at"] = today
                    disbursement_data["updated_at"] = today
                    disbursement_data["amount"] = Decimal(
                        disbursement_data["amount"]
                    ).quantize(Decimal("0.00"))
                    serializer = LoanDisbursementSerializer(data=disbursement_data)
                    serializer.is_valid(raise_exception=True)
                    serializer.save()
                    success_count += 1
                except Exception as e:
                    error_count += 1
                    errors.append(str(e))

        log.success_count = success_count
        log.error_count = error_count
        log.save()

        response_data = {
            "success_count": success_count,
            "error_count": error_count,
            "errors": errors,
        }

        return Response(
            response_data,
            status=(
                status.HTTP_201_CREATED
                if success_count > 0
                else status.HTTP_400_BAD_REQUEST
            ),
        )


class LoanDisbursementCSVUploadView(generics.CreateAPIView):
    pass