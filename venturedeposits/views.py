from rest_framework import generics
from rest_framework.response import Response
from rest_framework import status

from accounts.permissions import IsSystemAdminOrReadOnly
from venturedeposits.models import VentureDeposit
from venturedeposits.serializers import (
    VentureDepositSerializer,
    BulkVentureDepositSerializer,
)
from transactions.models import BulkTransactionLog
from django.db import transaction
from datetime import date
import csv
import io
import cloudinary.uploader
import logging
from decimal import Decimal
from venturetypes.models import VentureType

logger = logging.getLogger(__name__)


class VentureDepositListCreateView(generics.ListCreateAPIView):
    queryset = VentureDeposit.objects.all()
    serializer_class = VentureDepositSerializer
    permission_classes = [
        IsSystemAdminOrReadOnly,
    ]

    def perform_create(self, serializer):
        serializer.save(deposited_by=self.request.user)


class VentureDepositDetailView(generics.RetrieveAPIView):
    queryset = VentureDeposit.objects.all()
    serializer_class = VentureDepositSerializer
    permission_classes = [
        IsSystemAdminOrReadOnly,
    ]
    lookup_field = "reference"


class VentureDepositBulkUploadView(generics.CreateAPIView):
    """Upload CSV file for bulk venture deposits."""

    permission_classes = [IsSystemAdminOrReadOnly]
    serializer_class = VentureDepositSerializer

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

        # Get venture types
        venture_types = VentureType.objects.values_list("name", flat=True)
        if not venture_types:
            return Response(
                {"error": "No venture types defined."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Validate CSV columns
        account_columns = [f"{vt} Account" for vt in venture_types]
        amount_columns = [f"{vt} Amount" for vt in venture_types]
        required_columns = account_columns + amount_columns
        if not any(col in reader.fieldnames for col in required_columns):
            return Response(
                {
                    "error": f"CSV must include at least one venture type column pair (e.g., 'Venture A Account', 'Venture A Amount')."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        admin = request.user
        today = date.today()
        date_str = today.strftime("%Y%m%d")
        prefix = f"VENTURE-BULK-{date_str}"

        # Initialize log
        try:
            log = BulkTransactionLog.objects.create(
                admin=admin,
                transaction_type="Venture Deposits",
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
                public_id=f"bulk_venture/{prefix}_{file.name}",
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
                for venture_type in venture_types:
                    account_col = f"{venture_type} Account"
                    amount_col = f"{venture_type} Amount"
                    if (
                        account_col in row
                        and amount_col in row
                        and row[account_col]
                        and row[amount_col]
                    ):
                        try:
                            amount = float(row[amount_col])
                            if amount < Decimal("0.01"):
                                raise ValueError(f"{amount_col} must be greater than 0")
                            deposit_data = {
                                "venture_account": row[account_col],
                                "amount": amount,
                                "payment_method": row.get("Payment Method", "Cash"),
                            }
                            serializer = VentureDepositSerializer(data=deposit_data)
                            if serializer.is_valid():
                                deposit = serializer.save(deposited_by=admin)
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
