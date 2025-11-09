import csv
import io
import cloudinary.uploader
import logging
import calendar
from datetime import date
from django.db import transaction
from decimal import Decimal
from rest_framework.response import Response
from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from django.contrib.auth import get_user_model
from django.http import StreamingHttpResponse
from datetime import datetime
from collections import defaultdict
from django.db.models import Sum, Case, When, DecimalField, F
from django.db.models.functions import ExtractMonth, ExtractYear
from rest_framework.views import APIView

from savings.models import SavingsType
from ventures.models import VentureType
from transactions.serializers import AccountSerializer, MemberTransactionSerializer, MonthlySummarySerializer
from transactions.models import DownloadLog, BulkTransactionLog
from savings.serializers import SavingsDepositSerializer
from venturepayments.serializers import VenturePaymentSerializer
from venturedeposits.serializers import VentureDepositSerializer
from accounts.permissions import IsSystemAdminOrReadOnly
from loantypes.models import LoanType
from savingswithdrawals.models import SavingsWithdrawal
from savingsdeposits.models import SavingsDeposit
from venturepayments.models import VenturePayment
from venturedeposits.models import VentureDeposit
from ventures.models import VentureAccount
from loans.models import LoanAccount


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
        interest_only = (
            request.query_params.get("interest_only", "false").lower() == "true"
        )

        # Get savings, venture, and loan types
        savings_types = SavingsType.objects.values_list("name", flat=True)
        venture_types = VentureType.objects.values_list("name", flat=True)
        loan_types = LoanType.objects.values_list("name", flat=True)

        # Serialize data
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)
        data = serializer.data  # Directly use serializer.data (ReturnList)

        if interest_only:
            # Interest-only CSV
            headers = [
                "Member Number",
                "Member Name",
                "Loan Account",
                "Loan Type",
                "Interest Amount",
                "Outstanding Balance",
            ]
            buffer = io.StringIO()
            writer = csv.DictWriter(buffer, fieldnames=headers, lineterminator="\n")
            writer.writeheader()

            for user in data:
                for amount, acc_no, outstanding_balance in user["loan_interest"]:
                    loan_type = ""
                    for acc in user["loan_accounts"]:
                        if acc[0] == acc_no:
                            loan_type = acc[1]
                            break
                    if loan_type:
                        row = {
                            "Member Number": user["member_no"],
                            "Member Name": user["member_name"],
                            "Loan Account": acc_no,
                            "Loan Type": loan_type,
                            "Interest Amount": f"{amount:.2f}",
                            "Outstanding Balance": f"{outstanding_balance:.2f}",
                        }
                        writer.writerow(row)

            file_name = f"interest_transactions_{datetime.now().strftime('%Y%m%d')}.csv"
            cloudinary_path = f"interest_transactions/{file_name}"
        else:
            # Main account list CSV
            headers = ["Member Number", "Member Name"]
            for stype in savings_types:
                headers.extend([f"{stype} Account", f"{stype} Balance"])
            for vtype in venture_types:
                headers.extend([f"{vtype} Account", f"{vtype} Balance"])
            for ltype in loan_types:
                headers.extend([f"{ltype} Account", f"{ltype} Balance"])

            buffer = io.StringIO()
            writer = csv.DictWriter(buffer, fieldnames=headers, lineterminator="\n")
            writer.writeheader()

            for user in data:
                row = {
                    "Member Number": user["member_no"],
                    "Member Name": user["member_name"],
                }
                for stype in savings_types:
                    row[f"{stype} Account"] = ""
                    row[f"{stype} Balance"] = ""
                for vtype in venture_types:
                    row[f"{vtype} Account"] = ""
                    row[f"{vtype} Balance"] = ""
                for ltype in loan_types:
                    row[f"{ltype} Account"] = ""
                    row[f"{ltype} Balance"] = ""

                for acc_no, acc_type, balance in user["savings_accounts"]:
                    row[f"{acc_type} Account"] = acc_no
                    row[f"{acc_type} Balance"] = f"{balance:.2f}"

                for acc_no, acc_type, balance in user["venture_accounts"]:
                    row[f"{acc_type} Account"] = acc_no
                    row[f"{acc_type} Balance"] = f"{balance:.2f}"

                for acc_no, acc_type, outstanding_balance, _ in user["loan_accounts"]:
                    row[f"{acc_type} Account"] = acc_no
                    row[f"{acc_type} Balance"] = f"{outstanding_balance:.2f}"

                writer.writerow(row)

            file_name = f"account_list_{datetime.now().strftime('%Y%m%d')}.csv"
            cloudinary_path = f"account_lists/{file_name}"

        # Upload to Cloudinary
        buffer.seek(0)
        try:
            upload_result = cloudinary.uploader.upload(
                buffer,
                resource_type="raw",
                public_id=cloudinary_path,
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


class MemberYearlySummaryView(APIView):
    """
    Full member financial summary by year using member_no
    - Shows ALL types even if balance = 0
    - Year is dynamic: ?year=2024
    - No withdrawals
    - All deposits & payments listed
    - Chart of accounts with type-level totals
    """

    def get(self, request, member_no):
        year = int(request.query_params.get("year", datetime.now().year))

        # ------------------------------------------------------------------
        # 0. Get Member by member_no
        # ------------------------------------------------------------------
        try:
            member = User.objects.get(member_no=member_no, is_member=True)
        except User.DoesNotExist:
            return Response(
                {"error": "Member not found"}, status=status.HTTP_404_NOT_FOUND
            )

        # ------------------------------------------------------------------
        # 1. PRE-LOAD ALL TYPES (to show 0.0 if no activity)
        # ------------------------------------------------------------------
        all_savings_types = {t.name: Decimal("0.00") for t in SavingsType.objects.all()}
        all_venture_types = {t.name: Decimal("0.00") for t in VentureType.objects.all()}
        all_loan_types = {t.name: Decimal("0.00") for t in LoanType.objects.all()}

        # ------------------------------------------------------------------
        # 2. SAVINGS: Deposits only (by SavingsType)
        # ------------------------------------------------------------------
        savings_deposits = SavingsDeposit.objects.filter(
            savings_account__member=member, created_at__year=year
        ).select_related("savings_account__account_type")

        savings_by_type = defaultdict(Decimal)
        savings_deposit_list = []

        for dep in savings_deposits:
            savings_type = dep.savings_account.account_type.name
            amount = Decimal(str(dep.amount))
            savings_by_type[savings_type] += amount
            savings_deposit_list.append(
                {
                    "date": dep.created_at.strftime("%Y-%m-%d"),
                    "type": savings_type,
                    "amount": float(amount),
                    "ref": dep.reference or f"DEP{dep.id}",
                }
            )

        # Merge with all types → show 0.0 for missing
        final_savings_by_type = {
            k: float(savings_by_type.get(k, Decimal("0.00"))) for k in all_savings_types
        }

        total_savings = sum(final_savings_by_type.values())
        total_savings_deposits = total_savings

        # ------------------------------------------------------------------
        # 3. VENTURES: Deposits + Payments (by VentureType)
        # ------------------------------------------------------------------
        vent_deposits = VentureDeposit.objects.filter(
            venture_account__member=member, created_at__year=year
        ).select_related("venture_account__venture_type")

        vent_payments = VenturePayment.objects.filter(
            venture_account__member=member, created_at__year=year
        ).select_related("venture_account__venture_type")

        vent_dep_by_type = defaultdict(Decimal)
        vent_pay_by_type = defaultdict(Decimal)
        vent_deposit_list = []
        vent_payment_list = []

        for dep in vent_deposits:
            vtype = dep.venture_account.venture_type.name
            amount = Decimal(str(dep.amount))
            vent_dep_by_type[vtype] += amount
            vent_deposit_list.append(
                {
                    "date": dep.created_at.strftime("%Y-%m-%d"),
                    "type": vtype,
                    "amount": float(amount),
                    "ref": dep.reference or f"VDEP{dep.id}",
                }
            )

        for pay in vent_payments:
            vtype = pay.venture_account.venture_type.name
            amount = Decimal(str(pay.amount))
            vent_pay_by_type[vtype] += amount
            vent_payment_list.append(
                {
                    "date": pay.created_at.strftime("%Y-%m-%d"),
                    "type": vtype,
                    "amount": float(amount),
                    "ref": pay.reference or f"VPAY{pay.id}",
                }
            )

        # Merge with all types
        final_vent_dep_by_type = {
            k: float(vent_dep_by_type.get(k, Decimal("0.00")))
            for k in all_venture_types
        }
        final_vent_pay_by_type = {
            k: float(vent_pay_by_type.get(k, Decimal("0.00")))
            for k in all_venture_types
        }

        total_venture_deposits = sum(final_vent_dep_by_type.values())
        total_venture_payments = sum(final_vent_pay_by_type.values())
        total_ventures = total_venture_deposits - total_venture_payments

        # ------------------------------------------------------------------
        # 4. LOANS: Accounts, Disbursed, Outstanding (by LoanType)
        # ------------------------------------------------------------------
        loan_accounts = (
            LoanAccount.objects.filter(member=member)
            .select_related("loan_type")
            .prefetch_related("disbursements")
        )

        loan_list = []
        loan_disbursed_by_type = defaultdict(Decimal)
        loan_outstanding_by_type = defaultdict(Decimal)

        for loan in loan_accounts:
            disbursed = Decimal("0.00")
            for d in loan.disbursements.all():
                if d.disbursed_at and d.disbursed_at.year == year:
                    disbursed += Decimal(str(d.amount))

            outstanding = Decimal(str(loan.outstanding_balance or 0))
            loan_type = loan.loan_type.name

            loan_disbursed_by_type[loan_type] += disbursed
            loan_outstanding_by_type[loan_type] += outstanding

            loan_list.append(
                {
                    "account_no": loan.account_no,
                    "type": loan_type,
                    "disbursed": float(disbursed),
                    "outstanding": float(outstanding),
                }
            )

        # Merge with all types
        final_loan_disbursed = {
            k: float(loan_disbursed_by_type.get(k, Decimal("0.00")))
            for k in all_loan_types
        }
        final_loan_outstanding = {
            k: float(loan_outstanding_by_type.get(k, Decimal("0.00")))
            for k in all_loan_types
        }

        total_loans_disbursed = sum(final_loan_disbursed.values())
        total_loans_outstanding = sum(final_loan_outstanding.values())

        # ------------------------------------------------------------------
        # 5. CHART OF ACCOUNTS
        # ------------------------------------------------------------------
        chart_of_accounts = {
            "total_savings_all_types": float(total_savings),
            "savings_by_type": final_savings_by_type,
            "total_ventures_net": float(total_ventures),
            "ventures_by_type": {
                "deposits": final_vent_dep_by_type,
                "payments": final_vent_pay_by_type,
            },
            "total_loans_outstanding_all_types": float(total_loans_outstanding),
            "loans_outstanding_by_type": final_loan_outstanding,
            "total_loans_disbursed_all_types": float(total_loans_disbursed),
            "loans_disbursed_by_type": final_loan_disbursed,
            "total_deposits_made": float(
                total_savings_deposits + total_venture_deposits
            ),
        }

        # ------------------------------------------------------------------
        # 6. BUILD RESPONSE
        # ------------------------------------------------------------------
        response_data = {
            "year": year,
            "member_no": member.member_no,
            "member_name": member.get_full_name() or member.username,
            "summary": {
                "total_savings": float(total_savings),
                "total_savings_deposits": float(total_savings_deposits),
                "total_ventures": float(total_ventures),
                "total_venture_deposits": float(total_venture_deposits),
                "total_venture_payments": float(total_venture_payments),
                "total_loans_outstanding": float(total_loans_outstanding),
                "total_loans_disbursed": float(total_loans_disbursed),
            },
            "savings": {
                "by_type": final_savings_by_type,
                "deposits": savings_deposit_list,
            },
            "ventures": {
                "by_type": {
                    "deposits": final_vent_dep_by_type,
                    "payments": final_vent_pay_by_type,
                },
                "deposits": vent_deposit_list,
                "payments": vent_payment_list,
            },
            "loans": {
                "accounts": loan_list,
                "by_type": {
                    "total_disbursed": final_loan_disbursed,
                    "total_outstanding": final_loan_outstanding,
                },
            },
            "chart_of_accounts": chart_of_accounts,
        }

        return Response(response_data, status=status.HTTP_200_OK)
