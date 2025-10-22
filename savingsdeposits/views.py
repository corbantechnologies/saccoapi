from rest_framework import generics, status
from rest_framework.response import Response
from accounts.permissions import IsSystemAdminOrReadOnly
from savingsdeposits.models import SavingsDeposit
from savingsdeposits.serializers import (
    SavingsDepositSerializer,
    BulkSavingsDepositSerializer,
)
from savingsdeposits.utils import send_deposit_made_email
from datetime import date
from transactions.models import BulkTransactionLog
from django.db import transaction
from savingstypes.models import SavingsType
import csv
import io
import cloudinary.uploader
import logging
from decimal import Decimal

logger = logging.getLogger(__name__)


class SavingsDepositListCreateView(generics.ListCreateAPIView):
    queryset = SavingsDeposit.objects.all()
    serializer_class = SavingsDepositSerializer
    permission_classes = [IsSystemAdminOrReadOnly]

    def perform_create(self, serializer):
        deposit = serializer.save(deposited_by=self.request.user)
        # Send email to the account owner if they have an email address
        account_owner = deposit.savings_account.member
        if account_owner.email:
            send_deposit_made_email(account_owner, deposit)


class SavingsDepositView(generics.RetrieveAPIView):
    queryset = SavingsDeposit.objects.all()
    serializer_class = SavingsDepositSerializer
    permission_classes = [IsSystemAdminOrReadOnly]
    lookup_field = "reference"


"""
Bulk Transactions:
- With JSON payload
- With file upload (CSV)
"""


class BulkSavingsDepositView(generics.CreateAPIView):
    serializer_class = BulkSavingsDepositSerializer
    permission_classes = [IsSystemAdminOrReadOnly]

    def perform_create(self, serializer):
        deposits_data = serializer.validated_data.get("deposits", [])
        admin = self.request.user
        today = date.today()
        date_str = today.strftime("%Y%m%d")
        prefix = f"SAVINGS-BULK-{date_str}"

        # Initialize log
        log = BulkTransactionLog.objects.create(
            admin=admin,
            transaction_type="Savings Deposits",
            reference_prefix=prefix,
            success_count=0,
            error_count=0,
        )

        success_count = 0
        error_count = 0
        errors = []

        with transaction.atomic():
            for index, deposit_data in enumerate(deposits_data, 1):
                try:
                    # Add deposited_by and reference
                    deposit_data["deposited_by"] = admin
                    deposit_data["reference"] = f"{prefix}-{index:04d}"
                    deposit_data["transaction_status"] = deposit_data.get(
                        "transaction_status", "Completed"
                    )
                    deposit_data["is_active"] = deposit_data.get("is_active", True)

                    # Create deposit
                    deposit_serializer = SavingsDepositSerializer(data=deposit_data)
                    if deposit_serializer.is_valid():
                        deposit = deposit_serializer.save()
                        success_count += 1
                        # Send email if account owner has email
                        account_owner = deposit.savings_account.member
                        if account_owner.email:
                            send_deposit_made_email(account_owner, deposit)
                    else:
                        error_count += 1
                        errors.append(
                            {"index": index, "errors": deposit_serializer.errors}
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


class BulkSavingsDepositUploadView(generics.CreateAPIView):
    """Upload CSV file for bulk savings deposits."""

    permission_classes = [IsSystemAdminOrReadOnly]
    serializer_class = SavingsDepositSerializer  # Added for browsable API

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

        # Get savings types for validation
        try:
            savings_types = SavingsType.objects.all().values_list("name", flat=True)
        except Exception as e:
            logger.error(f"Failed to fetch savings types: {str(e)}")
            return Response(
                {"error": "Failed to fetch savings types"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        admin = request.user
        today = date.today()
        date_str = today.strftime("%Y%m%d")
        prefix = f"SAVINGS-BULK-{date_str}"

        # Initialize log
        try:
            log = BulkTransactionLog.objects.create(
                admin=admin,
                transaction_type="Savings Deposits",
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
                public_id=f"bulk_savings/{prefix}_{file.name}",
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
                try:
                    # Process each savings type
                    deposits_data = []
                    for stype in savings_types:
                        amount_key = f"{stype} Amount"
                        account_key = f"{stype} Account"
                        if amount_key in row and row[amount_key] and row[account_key]:
                            try:
                                amount = float(row[amount_key])
                                if amount < Decimal("0.01"):
                                    raise ValueError("Amount must be greater than 0")
                                deposit_data = {
                                    "savings_account": row[account_key],
                                    "amount": amount,
                                    "payment_method": row.get("Payment Method", "Cash"),
                                    "deposit_type": "Individual Deposit",
                                    "currency": "KES",
                                    "transaction_status": "Completed",
                                    "is_active": True,
                                }
                                deposits_data.append(deposit_data)
                            except ValueError as e:
                                error_count += 1
                                errors.append(
                                    {
                                        "row": index,
                                        "account": row.get(account_key),
                                        "error": str(e),
                                    }
                                )
                                continue

                    # Validate and save deposits
                    for deposit_data in deposits_data:
                        deposit_serializer = SavingsDepositSerializer(data=deposit_data)
                        if deposit_serializer.is_valid():
                            deposit = deposit_serializer.save(deposited_by=admin)
                            success_count += 1
                            account_owner = deposit.savings_account.member

                        else:
                            error_count += 1
                            errors.append(
                                {
                                    "row": index,
                                    "account": deposit_data["savings_account"],
                                    "error": str(deposit_serializer.errors),
                                }
                            )

                except Exception as e:
                    error_count += 1
                    errors.append({"row": index, "error": str(e)})

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

        # Return response
        response_data = {
            "success_count": success_count,
            "error_count": error_count,
            "errors": errors,
            "log_reference": log.reference_prefix,
            "cloudinary_url": log.cloudinary_url,
        }
        try:
            return Response(
                response_data,
                status=(
                    status.HTTP_201_CREATED
                    if success_count > 0
                    else status.HTTP_400_BAD_REQUEST
                ),
            )
        except Exception as e:
            logger.error(f"Failed to return response: {str(e)}")
            return Response(
                {"error": "Internal server error"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
