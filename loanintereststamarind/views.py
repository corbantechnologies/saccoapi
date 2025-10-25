import io
import csv
import logging
from decimal import Decimal
from datetime import date
from django.db import transaction
from rest_framework import generics, status
from rest_framework.response import Response
import cloudinary.uploader

from loanintereststamarind.models import TamarindLoanInterest
from loanintereststamarind.serializers import (
    TamarindLoanInterestSerializer,
    BulkTamarindLoanInterestSerializer,
)
from transactions.models import BulkTransactionLog
from accounts.permissions import IsSystemAdminOrReadOnly
from loantypes.models import LoanType
from loans.models import LoanAccount

logger = logging.getLogger(__name__)


class TamarindLoanInterestListCreateView(generics.ListCreateAPIView):
    queryset = TamarindLoanInterest.objects.all()
    serializer_class = TamarindLoanInterestSerializer
    permission_classes = (IsSystemAdminOrReadOnly,)

    def perform_create(self, serializer):
        serializer.save(entered_by=self.request.user)


class TamarindLoanInterestDetailView(generics.RetrieveAPIView):
    queryset = TamarindLoanInterest.objects.all()
    serializer_class = TamarindLoanInterestSerializer
    permission_classes = (IsSystemAdminOrReadOnly,)
    lookup_field = "reference"


class TamarindLoanInterestBulkUploadView(generics.CreateAPIView):
    """Upload CSV file for bulk loan interest entries."""

    permission_classes = [IsSystemAdminOrReadOnly]
    serializer_class = TamarindLoanInterestSerializer

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

        # Get loan types with manual interest
        loan_types = LoanType.objects.filter(
            system_calculates_interest=False
        ).values_list("name", flat=True)
        if not loan_types:
            return Response(
                {"error": "No loan types with manual interest calculation defined."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Validate CSV columns
        account_columns = [f"{lt} Account" for lt in loan_types]
        interest_columns = [f"{lt} Interest Amount" for lt in loan_types]
        required_columns = account_columns + interest_columns
        if not any(col in reader.fieldnames for col in required_columns):
            return Response(
                {
                    "error": f"CSV must include at least one loan type column pair (e.g., 'Personal Loan Account', 'Personal Loan Interest Amount')."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        admin = request.user
        today = date.today()
        date_str = today.strftime("%Y%m%d")
        prefix = f"LOAN-INTEREST-BULK-{date_str}"

        # Initialize log
        try:
            log = BulkTransactionLog.objects.create(
                admin=admin,
                transaction_type="Loan Interest Entries",
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
                public_id=f"bulk_loan_interest/{prefix}_{file.name}",
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
                    interest_col = f"{loan_type} Interest Amount"
                    if (
                        account_col in row
                        and interest_col in row
                        and row[account_col]
                        and row[interest_col]
                    ):
                        try:
                            amount = float(row[interest_col])
                            if amount < Decimal("0.01"):
                                raise ValueError(
                                    f"{interest_col} must be greater than 0"
                                )
                            interest_data = {
                                "loan_account": row[account_col],
                                "amount": amount,
                            }
                            serializer = TamarindLoanInterestSerializer(
                                data=interest_data
                            )
                            if serializer.is_valid():
                                interest = serializer.save(entered_by=admin)
                                # Update loan account interest accrued
                                interest.loan_account.interest_accrued += Decimal(
                                    str(amount)
                                )
                                interest.loan_account.save()
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
