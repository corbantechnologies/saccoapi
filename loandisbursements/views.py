import csv
import io
import cloudinary.uploader
import logging
from datetime import date
from django.db import transaction
from decimal import Decimal, InvalidOperation
from rest_framework.response import Response
from accounts.permissions import IsSystemAdminOrReadOnly
from rest_framework import generics, status

from transactions.models import BulkTransactionLog
from loandisbursements.models import LoanDisbursement
from loandisbursements.serializers import (
    LoanDisbursementSerializer,
    BulkLoanDisbursementSerializer,
)
from loans.models import LoanAccount
from loandisbursements.utils import send_disbursement_made_email


logger = logging.getLogger(__name__)


class LoanDisbursementListCreateView(generics.ListCreateAPIView):
    queryset = LoanDisbursement.objects.all()
    serializer_class = LoanDisbursementSerializer
    permission_classes = [IsSystemAdminOrReadOnly]

    def perform_create(self, serializer):
        disbursement = serializer.save(disbursed_by=self.request.user)
        # Send email to the account owner if they have an email address
        account_owner = disbursement.loan_account.member
        if account_owner.email:
            send_disbursement_made_email(account_owner, disbursement)


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
    """Upload CSV file for bulk loan disbursements — mirrors BulkSavingsDepositUploadView."""

    permission_classes = [IsSystemAdminOrReadOnly]
    serializer_class = LoanDisbursementSerializer

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

        # Required columns
        required_fields = {
            "loan_account_number",
            "amount",
            "currency",
            "transaction_status",
            "disbursement_type",
        }
        if not required_fields.issubset(reader.fieldnames):
            missing = required_fields - set(reader.fieldnames)
            return Response(
                {"error": f"Missing columns: {', '.join(missing)}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        admin = request.user
        today = date.today()
        date_str = today.strftime("%Y%m%d")
        prefix = f"LOAN-BULK-{date_str}"

        # Initialize log
        try:
            log = BulkTransactionLog.objects.create(
                admin=admin,
                transaction_type="Loan Disbursements",
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
                public_id=f"bulk_loan_disbursements/{prefix}_{file.name}",
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
            for index, row in enumerate(reader, start=1):
                try:
                    # Clean data
                    loan_account_number = row["loan_account_number"].strip()
                    amount_str = row["amount"].strip()
                    currency = row["currency"].strip().upper()
                    status_val = row["transaction_status"].strip().title()
                    disb_type = row["disbursement_type"].strip().title()

                    # Validate amount
                    try:
                        amount = Decimal(amount_str).quantize(Decimal("0.00"))
                        if amount <= 0:
                            raise ValueError("Amount must be > 0")
                    except (InvalidOperation, ValueError):
                        raise ValueError(f"Invalid amount: {amount_str}")

                    # Validate LoanAccount
                    try:
                        loan_account = LoanAccount.objects.get(
                            account_number=loan_account_number
                        )
                    except LoanAccount.DoesNotExist:
                        raise ValueError(
                            f"Loan account {loan_account_number} not found"
                        )

                    # Prepare disbursement data
                    disbursement_data = {
                        "loan_account": loan_account.id,
                        "amount": str(amount),
                        "currency": currency,
                        "transaction_status": status_val,
                        "disbursement_type": disb_type,
                        "disbursed_by": admin.id,
                        "reference": f"{prefix}-{index:04d}",
                        "created_at": today.isoformat(),
                        "updated_at": today.isoformat(),
                        "is_active": True,
                    }

                    # Validate & save
                    serializer = LoanDisbursementSerializer(data=disbursement_data)
                    if serializer.is_valid():
                        disbursement = serializer.save()
                        # Balance update is in model.save(), but we double-ensure
                        loan_account.outstanding_balance += amount
                        loan_account.save(update_fields=["outstanding_balance"])
                        success_count += 1
                    else:
                        error_count += 1
                        errors.append(
                            {
                                "row": index,
                                "account": loan_account_number,
                                "error": serializer.errors,
                            }
                        )

                except Exception as e:
                    error_count += 1
                    errors.append(
                        {
                            "row": index,
                            "account": row.get("loan_account_number", "Unknown"),
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
