from rest_framework import generics, status
import cloudinary.uploader
import csv
import io
from datetime import date
from decimal import Decimal
from django.db import transaction
import logging
from rest_framework.response import Response


from venturepayments.models import VenturePayment
from accounts.permissions import IsSystemAdminOrReadOnly
from venturepayments.serializers import VenturePaymentSerializer
from venturepayments.utils import (
    send_venture_payment_confirmation_email,
)

from transactions.models import BulkTransactionLog
from venturetypes.models import VentureType

logger = logging.getLogger(__name__)


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


class VenturePaymentBulkUploadView(generics.CreateAPIView):
    """Upload CSV file for bulk venture payments."""

    permission_classes = [IsSystemAdminOrReadOnly]
    serializer_class = VenturePaymentSerializer

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
        payment_columns = [f"{vt} Payment Amount" for vt in venture_types]
        required_columns = account_columns + payment_columns
        if not any(col in reader.fieldnames for col in required_columns):
            return Response(
                {
                    "error": f"CSV must include at least one venture type column pair (e.g., 'Venture A Account', 'Venture A Payment Amount')."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        admin = request.user
        today = date.today()
        date_str = today.strftime("%Y%m%d")
        prefix = f"VENTURE-PAYMENT-BULK-{date_str}"

        # Initialize log
        try:
            log = BulkTransactionLog.objects.create(
                admin=admin,
                transaction_type="Venture Payments",
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
                public_id=f"bulk_venture_payment/{prefix}_{file.name}",
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
                    payment_col = f"{venture_type} Payment Amount"
                    if (
                        account_col in row
                        and payment_col in row
                        and row[account_col]
                        and row[payment_col]
                    ):
                        try:
                            amount = float(row[payment_col])
                            if amount < Decimal("0.01"):
                                raise ValueError(
                                    f"{payment_col} must be greater than 0"
                                )
                            payment_data = {
                                "venture_account": row[account_col],
                                "amount": amount,
                                "payment_method": row.get("Payment Method", "Cash"),
                                "payment_type": row.get(
                                    "Payment Type", "Individual Settlement"
                                ),
                                "transaction_status": "Completed",
                            }
                            serializer = VenturePaymentSerializer(data=payment_data)
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
