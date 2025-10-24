import csv
import io
import cloudinary.uploader
import logging
from datetime import date
from django.db import transaction
from decimal import Decimal
from rest_framework.response import Response
from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from django.contrib.auth import get_user_model
from django.http import StreamingHttpResponse
from savings.models import SavingsType
from ventures.models import VentureType
from transactions.serializers import AccountSerializer
from datetime import datetime

from transactions.models import DownloadLog, BulkTransactionLog
from savings.serializers import SavingsDepositSerializer
from venturepayments.serializers import VenturePaymentSerializer
from venturedeposits.serializers import VentureDepositSerializer
from accounts.permissions import IsSystemAdminOrReadOnly
from loantypes.models import LoanType


logger = logging.getLogger(__name__)

User = get_user_model()


class AccountListView(generics.ListAPIView):
    serializer_class = AccountSerializer
    permission_classes = (IsAuthenticated,)

    def get_queryset(self):
        return (
            User.objects.all()
            .filter(is_member=True)
            .prefetch_related("savings_accounts", "venture_accounts")
        )


class AccountDetailView(generics.RetrieveAPIView):
    serializer_class = AccountSerializer
    permission_classes = (IsAuthenticated,)
    lookup_field = "member_no"

    def get_queryset(self):
        return (
            User.objects.all()
            .filter(is_member=True)
            .prefetch_related("savings_accounts", "venture_accounts")
        )


class AccountListDownloadView(generics.ListAPIView):
    serializer_class = AccountSerializer
    permission_classes = (IsAuthenticated,)

    def get_queryset(self):
        return (
            User.objects.all()
            .filter(is_member=True)
            .prefetch_related("savings_accounts", "venture_accounts", "loans")
        )

    def get(self, request, *args, **kwargs):
        # Get savings, venture, and loan types
        savings_types = SavingsType.objects.values_list("name", flat=True)
        venture_types = VentureType.objects.values_list("name", flat=True)
        loan_types = LoanType.objects.values_list("name", flat=True)

        # Define CSV headers
        headers = ["Member Number", "Member Name"]
        for stype in savings_types:
            headers.extend([f"{stype} Account", f"{stype} Balance"])
        for vtype in venture_types:
            headers.extend([f"{vtype} Account", f"{vtype} Balance"])
        for ltype in loan_types:
            headers.extend(
                [f"{ltype} Account", f"{ltype} Balance", f"{ltype} Interest"]
            )

        # CSV Buffer
        buffer = io.StringIO()
        writer = csv.DictWriter(buffer, fieldnames=headers, lineterminator="\n")
        writer.writeheader()

        # Serialize data
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)
        data = serializer.data  # Directly use serializer.data (ReturnList)

        # Write rows
        for user in data:
            row = {
                "Member Number": user["member_no"],
                "Member Name": user["member_name"],
            }
            # Initialize all fields as empty
            for stype in savings_types:
                row[f"{stype} Account"] = ""
                row[f"{stype} Balance"] = ""
            for vtype in venture_types:
                row[f"{vtype} Account"] = ""
                row[f"{vtype} Balance"] = ""
            for ltype in loan_types:
                row[f"{ltype} Account"] = ""
                row[f"{ltype} Balance"] = ""
                row[f"{ltype} Interest"] = ""

            # Populate savings accounts
            for acc_no, acc_type, balance in user["savings_accounts"]:
                row[f"{acc_type} Account"] = acc_no
                row[f"{acc_type} Balance"] = f"{balance:.2f}"

            # Populate venture accounts
            for acc_no, acc_type, balance in user["venture_accounts"]:
                row[f"{acc_type} Account"] = acc_no
                row[f"{acc_type} Balance"] = f"{balance:.2f}"

            # Populate loan accounts
            for acc_no, acc_type, outstanding_balance, _ in user["loan_accounts"]:
                row[f"{acc_type} Account"] = acc_no
                row[f"{acc_type} Balance"] = f"{outstanding_balance:.2f}"

            # Populate loan interest
            for amount, acc_no in user["loan_interest"]:
                for acc in user["loan_accounts"]:
                    if acc[0] == acc_no:
                        loan_type = acc[1]
                        row[f"{loan_type} Interest"] = f"{amount:.2f}"
                        break

            writer.writerow(row)

        # Upload to Cloudinary
        buffer.seek(0)
        file_name = f"account_list_{datetime.now().strftime('%Y%m%d')}.csv"
        try:
            upload_result = cloudinary.uploader.upload(
                buffer,
                resource_type="raw",
                public_id=f"account_lists/{file_name}",
                format="csv",
            )
        except Exception as e:
            logger.error(f"Cloudinary upload failed: {str(e)}")
            return Response(
                {"error": "Failed to upload file to storage"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        # Log the download
        try:
            DownloadLog.objects.create(
                admin=request.user,
                file_name=file_name,
                cloudinary_url=upload_result["secure_url"],
            )
        except Exception as e:
            logger.error(f"Failed to create DownloadLog: {str(e)}")
            return Response(
                {"error": "Failed to log download"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        # Prepare response
        buffer.seek(0)
        response = StreamingHttpResponse(buffer, content_type="text/csv")
        response["Content-Disposition"] = f"attachment; filename={file_name}"
        return response


class CombinedBulkUploadView(generics.CreateAPIView):
    permission_classes = [IsSystemAdminOrReadOnly]

    def post(self, request, *args, **kwargs):
        file = request.FILES.get("file")
        if not file:
            return Response(
                {"error": "No file uploaded."}, status=status.HTTP_400_BAD_REQUEST
            )

        # Read CSV
        try:
            csv_content = file.read().decode("utf-8")
            csv_file = io.StringIO(csv_content)
            reader = csv.DictReader(csv_file)
        except Exception as e:
            return Response(
                {"error": f"Invalid CSV file: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Get types for validation
        savings_types = SavingsType.objects.all().values_list("name", flat=True)
        venture_types = VentureType.objects.all().values_list("name", flat=True)

        # Validate CSV columns
        required_savings_columns = [f"{stype} Account" for stype in savings_types] + [
            f"{stype} Amount" for stype in savings_types
        ]
        required_venture_columns = (
            [f"{vtype} Account" for vtype in venture_types]
            + [f"{vtype} Amount" for vtype in venture_types]
            + [f"{vtype} Payment Amount" for vtype in venture_types]
        )
        if not any(
            col in reader.fieldnames
            for col in required_savings_columns + required_venture_columns
        ):
            return Response(
                {
                    "error": "CSV must include at least one valid column pair (e.g., 'Members Contribution Account', 'Members Contribution Amount' or 'Venture A Account', 'Venture A Amount'/'Venture A Payment Amount')."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        admin = request.user
        today = date.today()
        date_str = today.strftime("%Y%m%d")
        prefix = f"COMBINED-BULK-{date_str}"

        # Initialize log
        log = BulkTransactionLog.objects.create(
            admin=admin,
            transaction_type="Combined Bulk Updates",
            reference_prefix=prefix,
            success_count=0,
            error_count=0,
            file_name=file.name,
        )

        # Upload to Cloudinary
        buffer = io.StringIO(csv_content)
        upload_result = cloudinary.uploader.upload(
            buffer,
            resource_type="raw",
            public_id=f"bulk_combined/{prefix}_{file.name}",
            format="csv",
        )
        log.cloudinary_url = upload_result["secure_url"]
        log.save()

        success_count = 0
        error_count = 0
        errors = []

        with transaction.atomic():
            for index, row in enumerate(reader, 1):
                try:
                    # Process savings deposits
                    for stype in savings_types:
                        amount_key = f"{stype} Amount"
                        account_key = f"{stype} Account"
                        if amount_key in row and row[amount_key] and row[account_key]:
                            amount = float(row[amount_key])
                            if amount < Decimal("0.01"):
                                raise ValueError(f"{amount_key} must be greater than 0")
                            deposit_data = {
                                "savings_account": row[account_key],
                                "amount": amount,
                                "payment_method": row.get("Payment Method", "Cash"),
                                "deposit_type": "Individual Deposit",
                                "currency": "KES",
                                "transaction_status": "Completed",
                                "is_active": True,
                            }
                            deposit_serializer = SavingsDepositSerializer(
                                data=deposit_data
                            )
                            if deposit_serializer.is_valid():
                                deposit = deposit_serializer.save(deposited_by=admin)
                                success_count += 1
                                account_owner = deposit.savings_account.member
                                # if account_owner.email:
                                #     send_deposit_made_email(account_owner, deposit)
                            else:
                                error_count += 1
                                errors.append(
                                    {
                                        "row": index,
                                        "account": row[account_key],
                                        "error": str(deposit_serializer.errors),
                                    }
                                )

                    # Process venture deposits
                    for vtype in venture_types:
                        amount_key = f"{vtype} Amount"
                        account_key = f"{vtype} Account"
                        if amount_key in row and row[amount_key] and row[account_key]:
                            amount = float(row[amount_key])
                            if amount < Decimal("0.01"):
                                raise ValueError(f"{amount_key} must be greater than 0")
                            deposit_data = {
                                "venture_account": row[account_key],
                                "amount": amount,
                                "payment_method": row.get("Payment Method", "Cash"),
                            }
                            deposit_serializer = VentureDepositSerializer(
                                data=deposit_data
                            )
                            if deposit_serializer.is_valid():
                                deposit = deposit_serializer.save(deposited_by=admin)
                                success_count += 1
                                account_owner = deposit.venture_account.member
                                # if account_owner.email:
                                #     send_venture_deposit_made_email(account_owner, deposit)
                            else:
                                error_count += 1
                                errors.append(
                                    {
                                        "row": index,
                                        "account": row[account_key],
                                        "error": str(deposit_serializer.errors),
                                    }
                                )

                    # Process venture payments
                    for vtype in venture_types:
                        payment_key = f"{vtype} Payment Amount"
                        account_key = f"{vtype} Account"
                        if payment_key in row and row[payment_key] and row[account_key]:
                            amount = float(row[payment_key])
                            if amount < Decimal("0.01"):
                                raise ValueError(
                                    f"{payment_key} must be greater than 0"
                                )
                            payment_data = {
                                "venture_account": row[account_key],
                                "amount": amount,
                                "payment_method": row.get("Payment Method", "Cash"),
                                "payment_type": row.get(
                                    "Payment Type", "Individual Settlement"
                                ),
                                "transaction_status": "Completed",
                            }
                            payment_serializer = VenturePaymentSerializer(
                                data=payment_data
                            )
                            if payment_serializer.is_valid():
                                payment = payment_serializer.save(paid_by=admin)
                                success_count += 1
                                account_owner = payment.venture_account.member
                                # if account_owner.email:
                                #     send_venture_payment_confirmation_email(account_owner, payment)
                            else:
                                error_count += 1
                                errors.append(
                                    {
                                        "row": index,
                                        "account": row[account_key],
                                        "error": str(payment_serializer.errors),
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
