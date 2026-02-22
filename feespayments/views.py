from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView
from accounts.permissions import IsSystemAdminOrReadOnly
from feespayments.models import FeePayment
from memberfees.models import MemberFee
from feespayments.serializers import FeePaymentSerializer, BulkFeePaymentSerializer
from datetime import date
from transactions.models import BulkTransactionLog
from django.db import transaction
import csv
import io
import cloudinary.uploader
import logging
from decimal import Decimal

logger = logging.getLogger(__name__)

class FeePaymentListCreateView(generics.ListCreateAPIView):
    queryset = FeePayment.objects.all()
    serializer_class = FeePaymentSerializer
    permission_classes = [IsSystemAdminOrReadOnly]

    def perform_create(self, serializer):
        fee_payment = serializer.save(paid_by=self.request.user)

class FeePaymentView(generics.RetrieveAPIView):
    queryset = FeePayment.objects.all()
    serializer_class = FeePaymentSerializer
    permission_classes = [IsSystemAdminOrReadOnly]
    lookup_field = "reference"

class BulkFeePaymentView(generics.CreateAPIView):
    serializer_class = BulkFeePaymentSerializer
    permission_classes = [IsSystemAdminOrReadOnly]

    def perform_create(self, serializer):
        fee_payments_data = serializer.validated_data.get("fee_payments", [])
        admin = self.request.user
        today = date.today()
        date_str = today.strftime("%Y%m%d")
        prefix = f"FEE-PAYMENT-BULK-{date_str}"

        # Initialize log
        log = BulkTransactionLog.objects.create(
            admin=admin,
            transaction_type="Fee Payments",
            reference_prefix=prefix,
            success_count=0,
            error_count=0,
        )

        success_count = 0
        error_count = 0
        errors = []

        with transaction.atomic():
            for index, fee_payment_data in enumerate(fee_payments_data, 1):
                try:
                    # Add paid_by and reference
                    fee_payment_data["paid_by"] = admin
                    fee_payment_data["reference"] = f"{prefix}-{index:04d}"

                    # Create fee payment
                    fee_payment_serializer = FeePaymentSerializer(data=fee_payment_data)
                    if fee_payment_serializer.is_valid():
                        fee_payment_serializer.save()
                        success_count += 1
                    else:
                        error_count += 1
                        errors.append(
                            {"index": index, "errors": fee_payment_serializer.errors}
                        )
                except Exception as e:
                    error_count += 1
                    errors.append({"index": index, "error": str(e)})

            # Update log
            log.success_count = success_count
            log.error_count = error_count
            log.save()

        # Return response with summary
        response_data = {
            "success_count": success_count,
            "error_count": error_count,
            "errors": errors,
            "log_reference": log.reference_prefix,
        }
        return Response(
            response_data,
            status=(
                status.HTTP_201_CREATED
                if success_count > 0
                else status.HTTP_400_BAD_REQUEST
            ),
        )

class BulkFeePaymentUploadView(generics.CreateAPIView):
    """Upload CSV file for bulk fee payments."""

    permission_classes = [IsSystemAdminOrReadOnly]
    serializer_class = FeePaymentSerializer  # Added for browsable API

    def post(self, request, *args, **kwargs):
        file = request.FILES.get("file")
        if not file:
            return Response(
                {"error": "No file uploaded"}, status=status.HTTP_400_BAD_REQUEST
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

        admin = request.user
        today = date.today()
        date_str = today.strftime("%Y%m%d")
        prefix = f"FEE-PAYMENT-BULK-{date_str}"

        # Initialize log
        try:
            log = BulkTransactionLog.objects.create(
                admin=admin,
                transaction_type="Fee Payments",
                reference_prefix=prefix,
                success_count=0,
                error_count=0,
                file_name=file.name,
            )
        except Exception as e:
            logger.error(f"Failed to create log: {str(e)}")
            return Response(
                {"error": "Failed to create transaction log"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        success_count = 0
        error_count = 0
        errors = []
        created_fee_payments = []

        with transaction.atomic():
            for index, row in enumerate(reader, 1):
                try:
                    # Validate required fields
                    required_fields = ["member_fee", "amount", "payment_method"]
                    missing_fields = [f for f in required_fields if f not in row]
                    if missing_fields:
                        error_count += 1
                        errors.append(
                            {
                                "index": index,
                                "error": f"Missing required fields: {', '.join(missing_fields)}",
                            }
                        )
                        continue

                    # Validate member_fee
                    member_fee_id = row["member_fee"]
                    try:
                        member_fee = MemberFee.objects.get(id=member_fee_id)
                    except MemberFee.DoesNotExist:
                        error_count += 1
                        errors.append(
                            {
                                "index": index,
                                "error": f"MemberFee with ID {member_fee_id} not found",
                            }
                        )
                        continue

                    # Validate amount
                    try:
                        amount = Decimal(row["amount"])
                        if amount <= 0:
                            raise ValueError("Amount must be positive")
                    except (ValueError, TypeError):
                        error_count += 1
                        errors.append(
                            {
                                "index": index,
                                "error": f"Invalid amount: {row['amount']}",
                            }
                        )
                        continue

                    # Validate payment_method
                    payment_method = row["payment_method"].strip().upper()
                    if payment_method not in ["CASH", "MPESA", "CHEQUE", "BANK_TRANSFER"]:
                        error_count += 1
                        errors.append(
                            {
                                "index": index,
                                "error": f"Invalid payment method: {row['payment_method']}",
                            }
                        )
                        continue

                    # Validate receipt_number (optional)
                    receipt_number = row.get("receipt_number", "").strip()
                    if receipt_number and FeePayment.objects.filter(receipt_number=receipt_number).exists():
                        error_count += 1
                        errors.append(
                            {
                                "index": index,
                                "error": f"Receipt number {receipt_number} already exists",
                            }
                        )
                        continue

                    # Create fee payment
                    reference = f"{prefix}-{index:04d}"
                    fee_payment = FeePayment.objects.create(
                        member_fee=member_fee,
                        amount=amount,
                        payment_method=payment_method,
                        receipt_number=receipt_number or None,
                        reference=reference,
                        paid_by=admin,
                    )

                    created_fee_payments.append(fee_payment)
                    success_count += 1

                except Exception as e:
                    error_count += 1
                    errors.append({"index": index, "error": str(e)})

            # Update log
            log.success_count = success_count
            log.error_count = error_count
            log.save()

        # Serialize created fee payments
        serializer = FeePaymentSerializer(created_fee_payments, many=True)
        response_data = {
            "success_count": success_count,
            "error_count": error_count,
            "errors": errors,
            "log_reference": log.reference_prefix,
            "payments": serializer.data,
        }
        return Response(
            response_data,
            status=(
                status.HTTP_201_CREATED
                if success_count > 0
                else status.HTTP_400_BAD_REQUEST
            ),
        )