from rest_framework import generics, status
import io
import csv
import logging
from decimal import Decimal
from datetime import date
from django.db import transaction
from rest_framework.response import Response
import cloudinary.uploader

from accounts.permissions import IsSystemAdminOrReadOnly
from loanrepayments.models import LoanRepayment
from loanrepayments.serializers import LoanRepaymentSerializer
from transactions.models import BulkTransactionLog
from loans.models import LoanAccount
from loantypes.models import LoanType

logger = logging.getLogger(__name__)


class LoanRepaymentListCreateView(generics.ListCreateAPIView):
    queryset = LoanRepayment.objects.all()
    serializer_class = LoanRepaymentSerializer
    permission_classes = [
        IsSystemAdminOrReadOnly,
    ]

    def perform_create(self, serializer):
        serializer.save(paid_by=self.request.user)


class LoanRepaymentDetailView(generics.RetrieveAPIView):
    queryset = LoanRepayment.objects.all()
    serializer_class = LoanRepaymentSerializer
    permission_classes = [
        IsSystemAdminOrReadOnly,
    ]
    lookup_field = "reference"


class LoanRepaymentBulkUploadView(generics.CreateAPIView):
    """Upload CSV file for bulk loan repayments."""

    permission_classes = [IsSystemAdminOrReadOnly]
    serializer_class = LoanRepaymentSerializer

    def post(self, request, *args, **kwargs):
        file = request.FILES.get("file")
        if not file:
            return Response(
                {"error": "No file uploaded."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Read CSV
        try:
            csv_content = file.read().decode("utf-8")
            csv_file = io.StringIO(csv_content)
            reader = csv.DictReader(csv_file)
        except Exception as e:
            logger.error(f"Failed to read CSV: {str(e)}")
            return Response(
                {"error": f"Invalid CSV file: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Get loan types
        loan_types = LoanType.objects.values_list("name", flat=True)
        if not loan_types:
            return Response(
                {"error": "No loan types defined."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Validate CSV columns
        account_columns = [f"{lt} Account" for lt in loan_types]
        repayment_columns = [f"{lt} Repayment Amount" for lt in loan_types]
        required_columns = account_columns + repayment_columns
        if not any(col in reader.fieldnames for col in required_columns):
            return Response(
                {
                    "error": f"CSV must include at least one loan type column pair (e.g., 'Personal Loan Account', 'Personal Loan Repayment Amount')."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        admin = request.user
        today = date.today()
        date_str = today.strftime("%Y%m%d")
        prefix = f"LOAN-REPAYMENT-BULK-{date_str}"

        # Initialize log
        try:
            log = BulkTransactionLog.objects.create(
                admin=admin,
                transaction_type="Loan Repayments",
                reference_prefix=prefix,
                success_count=0,
                error_count=0,
                file_name=file.name,
            )
        except Exception as e:
            logger.error(f"Failed to create BulkTransactionLog: {str(e)}")
            return Response(
                {"error": "Failed to initialize transaction log"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        # Upload to Cloudinary
        try:
            buffer = io.StringIO(csv_content)
            upload_result = cloudinary.uploader.upload(
                buffer,
                resource_type="raw",
                public_id=f"bulk_loan_repayment/{prefix}_{file.name}",
                format="csv",
            )
            log.cloudinary_url = upload_result["secure_url"]
            log.save()
        except Exception as e:
            logger.error(f"Cloudinary upload failed: {str(e)}")
            return Response(
                {"error": "Failed to upload file to storage"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        success_count = 0
        error_count = 0
        errors = []

        with transaction.atomic():
            for index, row in enumerate(reader, 1):
                for loan_type in loan_types:
                    account_col = f"{loan_type} Account"
                    repayment_col = f"{loan_type} Repayment Amount"
                    if (
                        account_col in row
                        and repayment_col in row
                        and row[account_col]
                        and row[repayment_col]
                    ):
                        try:
                            amount = float(row[repayment_col])
                            if amount < Decimal("0.01"):
                                raise ValueError(
                                    f"{repayment_col} must be greater than 0"
                                )
                            repayment_data = {
                                "loan_account": row[account_col],
                                "amount": amount,
                                "payment_method": row.get("Payment Method", "Cash"),
                                "repayment_type": row.get(
                                    "Repayment Type", "Regular Repayment"
                                ),
                                "transaction_status": "Completed",
                            }
                            serializer = LoanRepaymentSerializer(data=repayment_data)
                            if serializer.is_valid():
                                serializer.save(paid_by=admin)
                                success_count += 1
                            else:
                                error_count += 1
                                errors.append(
                                    {
                                        "row": index,
                                        "account": row[account_col],
                                        "error": str(serializer.errors),
                                    }
                                )
                        except Exception as e:
                            error_count += 1
                            errors.append(
                                {
                                    "row": index,
                                    "account": row.get(account_col, "N/A"),
                                    "error": str(e),
                                }
                            )

            # Update log
            try:
                log.success_count = success_count
                log.error_count = error_count
                log.save()
            except Exception as e:
                logger.error(f"Failed to update BulkTransactionLog: {str(e)}")
                return Response(
                    {"error": "Failed to update transaction log"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )

        response_data = {
            "success_count": success_count,
            "error_count": error_count,
            "errors": errors,
            "log_reference": log.reference_prefix,
            "cloudinary_url": log.cloudinary_url,
        }
        return Response(
            response_data,
            status=(
                status.HTTP_201_CREATED
                if success_count > 0
                else status.HTTP_400_BAD_REQUEST
            ),
        )
