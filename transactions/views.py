import csv
import io
import asyncio
import cloudinary.uploader
import logging
import calendar
from playwright.async_api import async_playwright
from datetime import date
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.template.loader import render_to_string
from django.db import transaction
from decimal import Decimal
from rest_framework.response import Response
from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from django.contrib.auth import get_user_model
from django.http import StreamingHttpResponse
from datetime import datetime
from collections import defaultdict
from django.db.models import Sum, Q
from django.db.models.functions import TruncMonth
from rest_framework.views import APIView
from finances.models import GLAccount, JournalEntry


# ... (imports remain the same)


from savings.models import SavingsType
from ventures.models import VentureType
from transactions.serializers import (
    AccountSerializer,
    MonthlySummarySerializer,
    BulkUploadSerializer,
    MemberTransactionSerializer
)
from transactions.models import DownloadLog, BulkTransactionLog
from accounts.permissions import IsSystemAdminOrReadOnly
from loantypes.models import LoanType
from savingsdeposits.models import SavingsDeposit
from savingswithdrawals.models import SavingsWithdrawal
from venturepayments.models import VenturePayment
from venturedeposits.models import VentureDeposit
from ventures.models import VentureAccount
from loans.models import LoanAccount
from loanrepayments.models import LoanRepayment
from loanintereststamarind.models import TamarindLoanInterest
from feespayments.models import FeePayment
from memberfees.models import MemberFee
from feetypes.models import FeeType
from loandisbursements.models import LoanDisbursement
from savings.models import SavingsAccount
from guaranteerequests.models import GuaranteeRequest
from guarantorprofile.models import GuarantorProfile


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
        return User.objects.filter(is_member=True).prefetch_related(
            "savings_accounts",
            "venture_accounts",
            "loans",
            "loans__loan_disbursements",
            "loans__repayments",
            "loans__loan_interests__loan_account__loan_type",
        )

    def get(self, request, *args, **kwargs):
        interest_only = (
            request.query_params.get("interest_only", "false").lower() == "true"
        )

        # Load types
        savings_types = list(SavingsType.objects.values_list("name", flat=True))
        venture_types = list(VentureType.objects.values_list("name", flat=True))
        loan_types = list(LoanType.objects.values_list("name", flat=True))
        fee_types = list(FeeType.objects.values_list("name", flat=True))

        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)
        data = serializer.data

        buffer = io.StringIO()

        if interest_only:
            # === INTEREST-ONLY CSV (unchanged) ===
            headers = [
                "Member Number",
                "Member Name",
                "Loan Account",
                "Loan Type",
                "Interest Amount",
                "Outstanding Balance",
                "Date",
            ]
            writer = csv.DictWriter(buffer, fieldnames=headers, lineterminator="\n")
            writer.writeheader()

            for user in data:
                for amount, acc_no, lt_name, date in user["loan_interest"]:
                    out_bal = 0.0
                    for la_acc_no, _, la_out_bal in user["loan_accounts"]:
                        if la_acc_no == acc_no:
                            out_bal = float(la_out_bal)
                            break
                    writer.writerow(
                        {
                            "Member Number": user["member_no"],
                            "Member Name": user["member_name"],
                            "Loan Account": acc_no,
                            "Loan Type": lt_name,
                            "Interest Amount": f"{amount:.2f}",
                            "Outstanding Balance": f"{out_bal:.2f}",
                            "Date": date.strftime("%Y-%m-%d") if date else "",
                        }
                    )

            file_name = f"interest_transactions_{datetime.now():%Y%m%d}.csv"
            cloudinary_path = f"interest_transactions/{file_name}"

        else:
            # === FULL ACCOUNT LIST + BULK UPLOAD COLUMNS ===
            headers = ["Member Number", "Member Name"]

            # Savings: Account + Amount
            for st in savings_types:
                headers += [f"{st} Account", f"{st} Amount"]

            # Ventures: Account + Amount + Payment Amount
            for vt in venture_types:
                headers += [f"{vt} Account", f"{vt} Amount", f"{vt} Payment Amount"]

            # Loans: Account + Disbursement + Repayment + Interest
            for lt in loan_types:
                headers += [
                    f"{lt} Account",
                    f"{lt} Disbursement Amount",
                    f"{lt} Repayment Amount",
                    f"{lt} Interest Amount",
                ]

            # Fees
            for ft in fee_types:
                headers += [f"{ft} Account", f"{ft} Amount"]

            # Optional: Payment Method
            headers += ["Payment Method"]

            writer = csv.DictWriter(buffer, fieldnames=headers, lineterminator="\n")
            writer.writeheader()

            for user in data:
                row = {
                    "Member Number": user["member_no"],
                    "Member Name": user["member_name"],
                    "Payment Method": "Cash",  # Default
                }

                # Initialize all to empty
                for st in savings_types:
                    row[f"{st} Account"] = row[f"{st} Amount"] = ""
                for vt in venture_types:
                    row[f"{vt} Account"] = row[f"{vt} Amount"] = row[
                        f"{vt} Payment Amount"
                    ] = ""
                for lt in loan_types:
                    row[f"{lt} Account"] = row[f"{lt} Disbursement Amount"] = ""
                    row[f"{lt} Repayment Amount"] = row[f"{lt} Interest Amount"] = ""
                for ft in fee_types:
                    row[f"{ft} Account"] = row[f"{ft} Amount"] = ""

                # === Fill from existing data ===
                # Savings
                for acc_no, acc_type, balance in user["savings_accounts"]:
                    row[f"{acc_type} Account"] = acc_no
                    # Amount column stays blank for bulk edit

                # Ventures
                for acc_no, acc_type, balance in user["venture_accounts"]:
                    row[f"{acc_type} Account"] = acc_no

                # Loans
                loan_totals = {
                    lt: {"disb": 0.0, "rep": 0.0, "int": 0.0} for lt in loan_types
                }
                for acc_no, lt_name, out_bal in user["loan_accounts"]:
                    row[f"{lt_name} Account"] = acc_no

                # Fees
                # Note: Assuming MemberFee info is available in serialized user data.
                # If not, we'll need to update AccountSerializer.
                if "fees" in user:
                    for fee in user["fees"]:
                        row[f"{fee['fee_type_name']} Account"] = fee["account_number"]

                # Sum totals (for reference only — not used in bulk)
                for amt, _, lt_name, _ in user["loan_disbursements"]:
                    if lt_name in loan_totals:
                        loan_totals[lt_name]["disb"] += float(amt)
                for amt, _, lt_name, _ in user["loan_repayments"]:
                    if lt_name in loan_totals:
                        loan_totals[lt_name]["rep"] += float(amt)
                for amt, _, lt_name, _ in user["loan_interest"]:
                    if lt_name in loan_totals:
                        loan_totals[lt_name]["int"] += float(amt)

                # Optional: Show current totals in comments (or skip)
                # Not needed for bulk — admin will overwrite

                writer.writerow(row)

            file_name = f"bulk_upload_template_{datetime.now():%Y%m%d}.csv"
            cloudinary_path = f"bulk_templates/{file_name}"

        # === Upload to Cloudinary ===
        buffer.seek(0)
        upload_result = cloudinary.uploader.upload(
            buffer, resource_type="raw", public_id=cloudinary_path, format="csv"
        )

        # === Log ===
        DownloadLog.objects.create(
            admin=request.user,
            file_name=file_name,
            cloudinary_url=upload_result["secure_url"],
        )

        # === Return CSV ===
        buffer.seek(0)
        response = StreamingHttpResponse(buffer, content_type="text/csv")
        response["Content-Disposition"] = f'attachment; filename="{file_name}"'
        return response


class CombinedBulkUploadView(generics.CreateAPIView):
    serializer_class = BulkUploadSerializer
    permission_classes = [IsSystemAdminOrReadOnly]

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        file = serializer.validated_data["file"]
        csv_content = file.read().decode("utf-8")
        csv_file = io.StringIO(csv_content)
        reader = csv.DictReader(csv_file)

        # Load types
        savings_types = list(SavingsType.objects.values_list("name", flat=True))
        venture_types = list(VentureType.objects.values_list("name", flat=True))
        loan_types = list(LoanType.objects.values_list("name", flat=True))
        fee_types = list(FeeType.objects.values_list("name", flat=True))

        # Validate: At least one valid account column
        valid_pairs = 0
        for t in savings_types + venture_types + loan_types + fee_types:
            acc_col = f"{t} Account"
            if acc_col in reader.fieldnames:
                valid_pairs += 1
        if valid_pairs == 0:
            return Response(
                {"error": "CSV must include at least one '{Type} Account' column."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        admin = request.user
        today = date.today()
        prefix = f"COMBINED-BULK-{today:%Y%m%d}"

        log = BulkTransactionLog.objects.create(
            admin=admin,
            transaction_type="Combined Bulk",
            reference_prefix=prefix,
            file_name=file.name,
        )

        # Upload original file to Cloudinary
        buffer = io.StringIO(csv_content)
        upload_result = cloudinary.uploader.upload(
            buffer,
            resource_type="raw",
            public_id=f"bulk_combined/{prefix}_{file.name}",
            format="csv",
        )
        log.cloudinary_url = upload_result["secure_url"]
        log.save()

        success_count = error_count = 0
        errors = []

        with transaction.atomic():
            for idx, row in enumerate(reader, 1):
                try:
                    # === SAVINGS ===
                    for st in savings_types:
                        acc_key = f"{st} Account"
                        amt_key = f"{st} Amount"
                        if row.get(acc_key) and row.get(amt_key):
                            amount = Decimal(row[amt_key])
                            if amount <= 0:
                                raise ValueError(f"{amt_key} must be > 0")
                            SavingsDeposit.objects.create(
                                savings_account=SavingsAccount.objects.get(
                                    account_number=row[acc_key]
                                ),
                                amount=amount,
                                deposited_by=admin,
                                payment_method=row.get("Payment Method", "Cash"),
                                transaction_status="Completed",
                            )
                            success_count += 1

                    # === VENTURES ===
                    for vt in venture_types:
                        acc_key = f"{vt} Account"
                        dep_key = f"{vt} Amount"
                        pay_key = f"{vt} Payment Amount"
                        if row.get(acc_key):
                            if row.get(dep_key):
                                VentureDeposit.objects.create(
                                    venture_account=VentureAccount.objects.get(
                                        account_number=row[acc_key]
                                    ),
                                    amount=Decimal(row[dep_key]),
                                    deposited_by=admin,
                                )
                                success_count += 1
                            if row.get(pay_key):
                                VenturePayment.objects.create(
                                    venture_account=VentureAccount.objects.get(
                                        account_number=row[acc_key]
                                    ),
                                    amount=Decimal(row[pay_key]),
                                    paid_by=admin,
                                )
                                success_count += 1

                    # === LOANS ===
                    for lt in loan_types:
                        acc_key = f"{lt} Account"
                        disb_key = f"{lt} Disbursement Amount"
                        rep_key = f"{lt} Repayment Amount"
                        int_key = f"{lt} Interest Amount"

                        if row.get(acc_key):
                            loan_acc = LoanAccount.objects.get(
                                account_number=row[acc_key]
                            )

                            # Interest: optional
                            interest_val = row.get(int_key, "").strip()
                            if interest_val:
                                interest_amount = Decimal(interest_val)
                                if interest_amount < 0:
                                    raise ValueError("Interest cannot be negative")
                                TamarindLoanInterest.objects.create(
                                    loan_account=loan_acc,
                                    amount=interest_amount,
                                    entered_by=admin,
                                )
                                loan_acc.interest_accrued += interest_amount
                                success_count += 1

                            # Disbursement
                            if row.get(disb_key):
                                amount = Decimal(row[disb_key])
                                if amount <= 0:
                                    raise ValueError("Disbursement must be > 0")
                                LoanDisbursement.objects.create(
                                    loan_account=loan_acc,
                                    amount=amount,
                                    disbursed_by=admin,
                                    transaction_status="Completed",
                                )
                                loan_acc.outstanding_balance += amount
                                success_count += 1

                            # Repayment
                            if row.get(rep_key):
                                amount = Decimal(row[rep_key])
                                if amount <= 0:
                                    raise ValueError("Repayment must be > 0")
                                LoanRepayment.objects.create(
                                    loan_account=loan_acc,
                                    amount=amount,
                                    paid_by=admin,
                                    transaction_status="Completed",
                                )
                                loan_acc.outstanding_balance -= amount
                                success_count += 1

                            loan_acc.save()

                    # === FEES ===
                    for ft in fee_types:
                        acc_key = f"{ft} Account"
                        amt_key = f"{ft} Amount"
                        if row.get(acc_key) and row.get(amt_key):
                            amount = Decimal(row[amt_key])
                            if amount <= 0:
                                raise ValueError(f"{amt_key} must be > 0")
                            
                            member_fee = MemberFee.objects.get(account_number=row[acc_key])
                            FeePayment.objects.create(
                                member_fee=member_fee,
                                amount=amount,
                                paid_by=admin,
                                payment_method=row.get("Payment Method", "Cash"),
                                transaction_status="Completed",
                            )
                            success_count += 1

                except Exception as e:
                    error_count += 1
                    errors.append({"row": idx, "error": str(e)})

        log.success_count = success_count
        log.error_count = error_count
        log.save()

        return Response(
            {
                "success_count": success_count,
                "error_count": error_count,
                "errors": errors,
                "log_reference": log.reference_prefix,
                "cloudinary_url": log.cloudinary_url,
            },
            status=(
                status.HTTP_201_CREATED
                if success_count
                else status.HTTP_400_BAD_REQUEST
            ),
        )


# =================================================================================================
# MEMBER FINANCIAL SUMMARY
# =================================================================================================


class MemberYearlySummaryView(APIView):
    """
    Returns yearly + monthly financial summary with:
    - Correct month-end balances
    - Balances Brought Forward from prior year
    - Accurate running totals across years
    - Rich monthly totals + per-type totals + transactions
    - Total balance per section (savings, ventures, loans)
    """

    def get(self, request, member_no):
        year = int(request.query_params.get("year", datetime.now().year))
        member = get_object_or_404(User, member_no=member_no, is_member=True)

        # === PRELOAD ALL TYPES ===
        all_savings_types = {t.name: t for t in SavingsType.objects.all()}
        all_venture_types = {t.name: t for t in VentureType.objects.all()}
        all_loan_types = {t.name: t for t in LoanType.objects.all()}
        all_fee_types = {t.name: t for t in FeeType.objects.all()}

        # === FETCH MEMBER FEES FOR BALANCE TRACKING ===
        member_fees_qs = MemberFee.objects.filter(member=member).select_related("fee_type")
        member_fees_map = {f.fee_type.name: f for f in member_fees_qs}
        
        total_fees_outstanding = Decimal("0")
        for ftype in all_fee_types.values():
            mfee = member_fees_map.get(ftype.name)
            if mfee:
                total_fees_outstanding += mfee.remaining_balance
            else:
                total_fees_outstanding += ftype.standard_amount

        # === 1. FETCH PRIOR YEAR ENDING BALANCES (for B/F in January) ===
        prior_year = year - 1
        prior_balances = {
            "savings": {name: Decimal("0") for name in all_savings_types.keys()},
            "venture_net": {name: Decimal("0") for name in all_venture_types.keys()},
            "loan_out": {name: Decimal("0") for name in all_loan_types.keys()},
            "fee_out": {name: Decimal("0") for name in all_fee_types.keys()},
        }

        if prior_year >= 2020:
            # --- SAVINGS ---
            prior_savings = (
                SavingsDeposit.objects.filter(
                    savings_account__member=member,
                    created_at__year__lt=year,
                )
                .values("savings_account__account_type__name")
                .annotate(total=Sum("amount"))
            )
            for item in prior_savings:
                name = item["savings_account__account_type__name"]
                if name in prior_balances["savings"]:
                    prior_balances["savings"][name] = Decimal(str(item["total"]))

            # --- VENTURES ---
            prior_vent_deps = (
                VentureDeposit.objects.filter(
                    venture_account__member=member,
                    created_at__year__lt=year,
                )
                .values("venture_account__venture_type__name")
                .annotate(total=Sum("amount"))
            )
            prior_vent_pays = (
                VenturePayment.objects.filter(
                    venture_account__member=member,
                    created_at__year__lt=year,
                )
                .values("venture_account__venture_type__name")
                .annotate(total=Sum("amount"))
            )
            dep_map = {x["venture_account__venture_type__name"]: Decimal(str(x["total"])) for x in prior_vent_deps}
            pay_map = {x["venture_account__venture_type__name"]: Decimal(str(x["total"])) for x in prior_vent_pays}
            for name in all_venture_types.keys():
                prior_balances["venture_net"][name] = dep_map.get(name, Decimal("0")) - pay_map.get(name, Decimal("0"))

            # --- LOANS ---
            prior_disb = (
                LoanDisbursement.objects.filter(
                    loan_account__member=member,
                    created_at__year__lt=year,
                    transaction_status="Completed",
                )
                .values("loan_account__loan_type__name")
                .annotate(total=Sum("amount"))
            )
            prior_rep = (
                LoanRepayment.objects.filter(
                    loan_account__member=member,
                    created_at__year__lt=year,
                    transaction_status="Completed",
                    repayment_type__in=[
                        "Regular Repayment", "Early Settlement", "Partial Payment", "Individual Settlement"
                    ],
                )
                .values("loan_account__loan_type__name")
                .annotate(total=Sum("amount"))
            )
            disb_map = {x["loan_account__loan_type__name"]: Decimal(str(x["total"])) for x in prior_disb}
            rep_map = {x["loan_account__loan_type__name"]: Decimal(str(x["total"])) for x in prior_rep}
            for name in all_loan_types.keys():
                disb = disb_map.get(name, Decimal("0"))
                rep = rep_map.get(name, Decimal("0"))
                prior_balances["loan_out"][name] = max(disb - rep, Decimal("0"))

            # --- FEES ---
            prior_fee_pays_qs = (
                FeePayment.objects.filter(
                    member_fee__member=member,
                    created_at__year__lt=year,
                )
                .values("member_fee__fee_type__name")
                .annotate(total=Sum("amount"))
            )
            fee_pay_map = {x["member_fee__fee_type__name"]: Decimal(str(x["total"])) for x in prior_fee_pays_qs}
            for name, ftype in all_fee_types.items():
                mfee = member_fees_map.get(name)
                billed = mfee.amount if mfee else ftype.standard_amount
                creation_year = mfee.created_at.year if mfee else 1900
                billed_prior = billed if creation_year < year else Decimal("0")
                pay = fee_pay_map.get(name, Decimal("0"))
                prior_balances["fee_out"][name] = max(billed_prior - pay, Decimal("0"))

        # === 2. INITIALIZE RUNNING BALANCES WITH PRIOR YEAR ===
        running = {
            "savings": prior_balances["savings"].copy(),
            "venture_net": prior_balances["venture_net"].copy(),
            "loan_out": prior_balances["loan_out"].copy(),
            "fee_out": prior_balances["fee_out"].copy(),
        }  # type: dict[str, dict[str, Decimal]]

        # === YEARLY ACCUMULATORS ===
        yearly = {
            "savings": {name: Decimal("0") for name in all_savings_types.keys()},
            "vent_dep": {name: Decimal("0") for name in all_venture_types.keys()},
            "vent_pay": {name: Decimal("0") for name in all_venture_types.keys()},
            "loan_disb": {name: Decimal("0") for name in all_loan_types.keys()},
            "loan_rep": {name: Decimal("0") for name in all_loan_types.keys()},
            "loan_int": {name: Decimal("0") for name in all_loan_types.keys()},
            "fee_income": {name: Decimal("0") for name in all_fee_types.keys() if all_fee_types[name].is_income},
            "member_contributions": {name: Decimal("0") for name in all_fee_types.keys() if not all_fee_types[name].is_income},
            "guarantees": {"new": Decimal("0")},
        }  # type: dict[str, dict[str, Decimal]]

        # === FETCH GUARANTOR PROFILE ===
        try:
            guarantor_profile = GuarantorProfile.objects.get(member=member)
            total_active_guarantees = guarantor_profile.committed_guarantee_amount
        except GuarantorProfile.DoesNotExist:
            total_active_guarantees = Decimal("0")

        # === OPTIMIZED FETCHING: ALL YEAR DATA AT ONCE ===
        from django.db.models.functions import TruncMonth

        # Helper to group by month
        def get_monthly_data(queryset, date_field="created_at"):
            return (
                queryset
                .annotate(month=TruncMonth(date_field))
                .order_by("month")
            )

        # 1. Savings
        savings_qs = get_monthly_data(
            SavingsDeposit.objects.filter(
                savings_account__member=member,
                created_at__year=year
            ).select_related("savings_account__account_type")
        )
        # Group in Python to avoid overly complex potential grouping key issues if we need transaction lists
        # But for summation we could use values().annotate(). 
        # However, we NEED the transaction list details for the 'view details' part of the summary.
        # So we fetch all transactions for the year (one query per model) and group in Python.
        # This is strictly better than 12 queries per model.

        savings_by_month = {}  # type: dict[int, list]
        for dep in savings_qs:
            m = dep.month.month
            if m not in savings_by_month:
                savings_by_month[m] = []
            savings_by_month[m].append(dep)

        # 2. Ventures
        vent_dep_qs = get_monthly_data(
            VentureDeposit.objects.filter(
                venture_account__member=member,
                created_at__year=year
            ).select_related("venture_account__venture_type")
        )
        vent_pay_qs = get_monthly_data(
            VenturePayment.objects.filter(
                venture_account__member=member,
                created_at__year=year
            ).select_related("venture_account__venture_type")
        )
        vent_dep_by_month = {}  # type: dict[int, list]
        for d in vent_dep_qs:
            m = d.month.month
            if m not in vent_dep_by_month:
                vent_dep_by_month[m] = []
            vent_dep_by_month[m].append(d)
        
        vent_pay_by_month = {}  # type: dict[int, list]
        for p in vent_pay_qs:
            m = p.month.month
            if m not in vent_pay_by_month:
                vent_pay_by_month[m] = []
            vent_pay_by_month[m].append(p)

        # 3. Loans
        loan_disb_qs = get_monthly_data(
            LoanDisbursement.objects.filter(
                loan_account__member=member,
                created_at__year=year,
                transaction_status="Completed",
            ).select_related("loan_account__loan_type")
        )
        loan_rep_qs = get_monthly_data(
            LoanRepayment.objects.filter(
                loan_account__member=member,
                created_at__year=year,
                transaction_status="Completed",
            ).select_related("loan_account__loan_type")
        )
        loan_int_qs = get_monthly_data(
            TamarindLoanInterest.objects.filter(
                loan_account__member=member,
                created_at__year=year,
            ).select_related("loan_account__loan_type")
        )

        loan_disb_by_month = {}  # type: dict[int, list]
        for d in loan_disb_qs:
            m = d.month.month
            if m not in loan_disb_by_month:
                loan_disb_by_month[m] = []
            loan_disb_by_month[m].append(d)

        loan_rep_by_month = {}  # type: dict[int, list]
        for r in loan_rep_qs:
            m = r.month.month
            if m not in loan_rep_by_month:
                loan_rep_by_month[m] = []
            loan_rep_by_month[m].append(r)
            
        loan_int_by_month = {}  # type: dict[int, list]
        for i in loan_int_qs:
            m = i.month.month
            if m not in loan_int_by_month:
                loan_int_by_month[m] = []
            loan_int_by_month[m].append(i)

        # 4. Guarantees
        new_guarantees_qs = get_monthly_data(
            GuaranteeRequest.objects.filter(
                guarantor__member=member,
                status="Accepted",
                created_at__year=year,
            ).select_related("member")
        )
        guarantees_by_month = {}  # type: dict[int, list]
        for g in new_guarantees_qs:
            m = g.month.month
            if m not in guarantees_by_month:
                guarantees_by_month[m] = []
            guarantees_by_month[m].append(g)

        # 5. Fees
        fees_qs = get_monthly_data(
            FeePayment.objects.filter(
                member_fee__member=member,
                created_at__year=year
            ).select_related("member_fee__fee_type")
        )
        fees_by_month = {}  # type: dict[int, list]
        for f in fees_qs:
            m = f.month.month
            if m not in fees_by_month:
                fees_by_month[m] = []
            fees_by_month[m].append(f)

        monthly_summary = []

        # === 3. LOOP THROUGH EACH MONTH (PROCESSING ONLY) ===
        for month in range(1, 13):
            month_name = calendar.month_name[month]
            month_key = f"{month_name} {year}"

            # === SAVINGS ===
            savings_deps = savings_by_month.get(month, [])
            savings_by_type = {}  # type: dict[str, dict]
            
            for dep in savings_deps:
                # type: ignore
                stype = dep.savings_account.account_type.name
                amount = Decimal(str(dep.amount))
                if stype not in savings_by_type:
                    savings_by_type[stype] = {"total": Decimal("0"), "deposits": []}
                savings_by_type[stype]["total"] += amount # type: ignore
                savings_by_type[stype]["deposits"].append({"type": stype, "amount": float(amount)}) # type: ignore
                
                s_yearly = yearly["savings"]
                s_yearly[stype] = s_yearly.get(stype, Decimal("0")) + amount # type: ignore

            # === VENTURES ===
            vent_deps = vent_dep_by_month.get(month, [])
            vent_pays = vent_pay_by_month.get(month, [])

            vent_by_type = {}  # type: dict[str, dict]
            for dep in vent_deps:
                # type: ignore
                vtype = dep.venture_account.venture_type.name
                amount = Decimal(str(dep.amount))
                if vtype not in vent_by_type:
                    vent_by_type[vtype] = {"deposits": [], "payments": []}
                vent_by_type[vtype]["deposits"].append({"venture_type": vtype, "amount": float(amount)}) # type: ignore
                
                v_yearly = yearly["vent_dep"]
                v_yearly[vtype] = v_yearly.get(vtype, Decimal("0")) + amount # type: ignore

            for pay in vent_pays:
                # type: ignore
                vtype = pay.venture_account.venture_type.name
                amount = Decimal(str(pay.amount))
                if vtype not in vent_by_type:
                    vent_by_type[vtype] = {"deposits": [], "payments": []}
                vent_by_type[vtype]["payments"].append({"venture_type": vtype, "amount": float(amount)}) # type: ignore
                
                vp_yearly = yearly["vent_pay"]
                vp_yearly[vtype] = vp_yearly.get(vtype, Decimal("0")) + amount # type: ignore

            # === LOANS ===
            disbursements = loan_disb_by_month.get(month, [])
            repayments = loan_rep_by_month.get(month, [])
            interests = loan_int_by_month.get(month, [])

            loan_by_type = {}  # type: dict[str, dict]
            for d in disbursements:
                # type: ignore
                ltype = d.loan_account.loan_type.name
                amount = Decimal(str(d.amount))
                if ltype not in loan_by_type:
                    loan_by_type[ltype] = {"disbursed": [], "repaid": [], "interest": []}
                loan_by_type[ltype]["disbursed"].append({"loan_type": ltype, "amount": float(amount)}) # type: ignore
                
                ld_yearly = yearly["loan_disb"]
                ld_yearly[ltype] = ld_yearly.get(ltype, Decimal("0")) + amount # type: ignore

            for r in repayments:
                # type: ignore
                ltype = r.loan_account.loan_type.name
                amount = Decimal(str(r.amount))
                if ltype not in loan_by_type:
                    loan_by_type[ltype] = {"disbursed": [], "repaid": [], "interest": []}
                if r.repayment_type != "Interest Payment":
                    loan_by_type[ltype]["repaid"].append({"loan_type": ltype, "amount": float(amount)})
                    
                    lr_yearly = yearly["loan_rep"]
                    lr_yearly[ltype] = lr_yearly.get(ltype, Decimal("0")) + amount

            for i in interests:
                # type: ignore
                ltype = i.loan_account.loan_type.name
                amount = Decimal(str(i.amount))
                if ltype not in loan_by_type:
                    loan_by_type[ltype] = {"disbursed": [], "repaid": [], "interest": []}
                loan_by_type[ltype]["interest"].append({"loan_type": ltype, "amount": float(amount)}) # type: ignore
                
                li_yearly = yearly["loan_int"]
                li_yearly[ltype] = li_yearly.get(ltype, Decimal("0")) + amount # type: ignore

            # === FEES ===
            fees = fees_by_month.get(month, [])
            fees_by_type = {}  # type: dict[str, dict]
            income_fees_month = Decimal("0")
            contributions_month = Decimal("0")

            for f in fees:
                # type: ignore
                ftype = f.member_fee.fee_type.name
                is_income = f.member_fee.fee_type.is_income
                amount = Decimal(str(f.amount))
                
                if ftype not in fees_by_type:
                    fees_by_type[ftype] = {"total": Decimal("0"), "payments": [], "is_income": is_income}
                
                fees_by_type[ftype]["total"] += amount # type: ignore
                fees_by_type[ftype]["payments"].append({"type": ftype, "amount": float(amount)}) # type: ignore
                
                if is_income:
                    yearly["fee_income"][ftype] = yearly["fee_income"].get(ftype, Decimal("0")) + amount
                    income_fees_month += amount
                else:
                    yearly["member_contributions"][ftype] = yearly["member_contributions"].get(ftype, Decimal("0")) + amount
                    contributions_month += amount

            # === GUARANTEES (NEW) ===
            new_guarantees = guarantees_by_month.get(month, [])
            guarantee_data = {"total_new": Decimal("0"), "transactions": []}
            for gr in new_guarantees:
                # type: ignore
                amount = Decimal(str(gr.guaranteed_amount))
                current = Decimal(str(gr.current_balance if gr.current_balance is not None else amount))
                guarantee_data["total_new"] += amount
                
                g_yearly = yearly["guarantees"]
                g_yearly["new"] = g_yearly.get("new", Decimal("0")) + amount # type: ignore
                
                guarantee_data["transactions"].append({ # type: ignore
                    "borrower_name": f"{gr.member.first_name} {gr.member.last_name}",
                    "borrower_no": gr.member.member_no,
                    "amount": float(amount),
                    "current_balance": float(current),
                    "date": gr.created_at.strftime("%Y-%m-%d"),
                })

            # === UPDATE RUNNING BALANCES ===
            # if a fee was billed this month, add to running balance before subtracting payments
            for name, ftype in all_fee_types.items():
                mfee = member_fees_map.get(name)
                creation_year = mfee.created_at.year if mfee else 1900
                creation_month = mfee.created_at.month if mfee else 1
                billed = mfee.amount if mfee else ftype.standard_amount
                
                # if billed exactly in this month, running increases
                if creation_year == year and creation_month == month:
                    running["fee_out"][name] = Decimal(str(running["fee_out"].get(name, 0))) + billed

            for name, data in savings_by_type.items():
                r_savings = running["savings"]
                r_savings[name] = Decimal(str(r_savings.get(name, 0))) + Decimal(str(data["total"]))  # type: ignore
            for name, data in vent_by_type.items():
                dep = sum([Decimal(str(d["amount"])) for d in data.get("deposits", [])]) # type: ignore
                pay = sum([Decimal(str(p["amount"])) for p in data.get("payments", [])]) # type: ignore
                r_vent = running["venture_net"]
                r_vent[name] = Decimal(str(r_vent.get(name, 0))) + (dep - pay)  # type: ignore
            for name, data in loan_by_type.items():
                disb = sum([Decimal(str(d["amount"])) for d in data.get("disbursed", [])]) # type: ignore
                rep = sum([Decimal(str(r["amount"])) for r in data.get("repaid", [])]) # type: ignore
                r_loan = running["loan_out"]
                r_loan[name] = Decimal(str(r_loan.get(name, 0))) + (disb - rep)  # type: ignore

            for name, data in fees_by_type.items():
                pay = Decimal(str(data["total"]))
                r_fee = running["fee_out"]
                r_fee[name] = max(Decimal(str(r_fee.get(name, 0))) - pay, Decimal("0"))

            # === CALCULATE MONTHLY TOTALS ===
            total_savings_month = sum([Decimal(str(v["total"])) for v in savings_by_type.values()])
            total_vent_dep_month = sum([sum([Decimal(str(d["amount"])) for d in data["deposits"]]) for data in vent_by_type.values()])
            total_vent_pay_month = sum([sum([Decimal(str(p["amount"])) for p in data["payments"]]) for data in vent_by_type.values()])
            total_vent_balance_month = total_vent_dep_month - total_vent_pay_month

            total_loan_disb_month = sum([sum([Decimal(str(d["amount"])) for d in data["disbursed"]]) for data in loan_by_type.values()])
            total_loan_rep_month = sum([sum([Decimal(str(r["amount"])) for r in data["repaid"]]) for data in loan_by_type.values()])
            total_loan_int_month = sum([sum([Decimal(str(i["amount"])) for i in data["interest"]]) for data in loan_by_type.values()])
            total_loan_out_month = sum([Decimal(str(v)) for v in running["loan_out"].values()])

            # === ENHANCE by_type WITH TOTALS ===
            enhanced_savings = []
            for name in all_savings_types.keys():
                data = savings_by_type.get(name, {"total": Decimal("0"), "deposits": []})
                monthly_total = Decimal(str(data["total"]))
                r_savings = running["savings"]
                brought = Decimal(str(r_savings.get(name, 0))) - monthly_total
                enhanced_savings.append({
                    "type": name,
                    "amount": float(monthly_total),
                    "total_deposits": float(monthly_total),
                    "deposits": data["deposits"],
                    "balance_brought_forward": float(brought),
                    "balance_carried_forward": float(r_savings.get(name, 0)),
                })

            enhanced_ventures = []
            for name in all_venture_types.keys():
                data = vent_by_type.get(name, {"deposits": [], "payments": []})
                dep_total = sum([Decimal(str(d["amount"])) for d in data.get("deposits", [])]) # type: ignore
                pay_total = sum([Decimal(str(p["amount"])) for p in data.get("payments", [])]) # type: ignore
                net_month = dep_total - pay_total
                r_vent = running["venture_net"]
                brought = Decimal(str(r_vent.get(name, 0))) - net_month
                enhanced_ventures.append({
                    "venture_type": name,
                    "total_venture_deposits": float(dep_total),
                    "total_venture_payments": float(pay_total),
                    "venture_deposits_transactions": data.get("deposits", []), # type: ignore
                    "venture_payments_transactions": data.get("payments", []), # type: ignore
                    "balance_brought_forward": float(brought),
                    "balance_carried_forward": float(r_vent.get(name, 0)),
                })

            enhanced_loans = []
            for name in all_loan_types.keys():
                data = loan_by_type.get(name, {"disbursed": [], "repaid": [], "interest": []})
                disb_total = sum([Decimal(str(d["amount"])) for d in data.get("disbursed", [])]) # type: ignore
                rep_total = sum([Decimal(str(r["amount"])) for r in data.get("repaid", [])]) # type: ignore
                int_total = sum([Decimal(str(i["amount"])) for i in data.get("interest", [])]) # type: ignore
                net_month = disb_total - rep_total
                r_loan = running["loan_out"]
                brought = Decimal(str(r_loan.get(name, 0))) - net_month
                enhanced_loans.append({
                    "loan_type": name,
                    "total_amount_disbursed": float(disb_total),
                    "total_amount_repaid": float(rep_total),
                    "total_interest_charged": float(int_total),
                    "total_amount_outstanding": float(r_loan.get(name, 0)),
                    "total_amount_disbursed_transactions": data.get("disbursed", []), # type: ignore
                    "total_amount_repaid_transactions": data.get("repaid", []), # type: ignore
                    "total_interest_charged_transactions": data.get("interest", []), # type: ignore
                    "balance_brought_forward": float(brought),
                    "balance_carried_forward": float(r_loan.get(name, 0)),
                })

            enhanced_fees = []
            for name in all_fee_types.keys():
                data = fees_by_type.get(name, {"total": Decimal("0"), "payments": []})
                pay_total = Decimal(str(data["total"]))
                
                mfee = member_fees_map.get(name)
                creation_year = mfee.created_at.year if mfee else 1900
                creation_month = mfee.created_at.month if mfee else 1
                billed = mfee.amount if mfee else all_fee_types[name].standard_amount
                
                # Billed this month?
                billed_month = billed if (creation_year == year and creation_month == month) else Decimal("0")
                
                r_fee = running["fee_out"]
                net_month = billed_month - pay_total
                brought = Decimal(str(r_fee.get(name, 0))) - net_month
                
                enhanced_fees.append({
                    "fee_type": name,
                    "total_expected": float(billed),
                    "total_amount_paid": float(pay_total),
                    "total_amount_outstanding": float(r_fee.get(name, 0)),
                    "payments": data["payments"],
                    "balance_brought_forward": float(brought),
                    "balance_carried_forward": float(r_fee.get(name, 0)),
                })

            # === APPEND MONTH WITH FULL SUMMARY + TOTAL BALANCE ===
            monthly_summary.append({
                "month": month_key,
                "savings": {
                    "total_savings": float(total_savings_month),
                    "total_savings_deposits": float(total_savings_month),
                    "total_balance": float(sum([Decimal(str(v)) for v in running["savings"].values()])),
                    "by_type": enhanced_savings,
                },
                "ventures": {
                    "venture_deposits": float(total_vent_dep_month),
                    "venture_payments": float(total_vent_pay_month),
                    "venture_balance": float(total_vent_balance_month),
                    "total_balance": float(sum([Decimal(str(v)) for v in running["venture_net"].values()])),
                    "by_type": enhanced_ventures,
                },
                "loans": {
                    "total_loans_disbursed": float(total_loan_disb_month),
                    "total_loans_repaid": float(total_loan_rep_month),
                    "total_interest_charged": float(total_loan_int_month),
                    "total_loans_outstanding": float(total_loan_out_month),
                    "total_balance": float(total_loan_out_month),
                    "by_type": enhanced_loans,
                },
                "guarantees": {
                    "new_guarantees": float(guarantee_data["total_new"]),
                    "transactions": guarantee_data["transactions"]
                },
                "fees": {
                    "fee_income": float(income_fees_month),
                    "member_contributions": float(contributions_month),
                    "by_type": enhanced_fees,
                },
            })

        # === YEARLY TOTALS ===
        total_savings = sum(yearly["savings"].values())
        total_vent_dep = sum(yearly["vent_dep"].values())
        total_vent_pay = sum(yearly["vent_pay"].values())
        total_ventures_net = total_vent_dep - total_vent_pay
        total_loan_disb = sum(yearly["loan_disb"].values())
        total_loan_rep = sum(yearly["loan_rep"].values())
        total_loan_int = sum(yearly["loan_int"].values())
        total_loan_out = sum(running["loan_out"].values())
        total_fee_income = sum(yearly["fee_income"].values())
        total_member_contributions = sum(yearly["member_contributions"].values())
        total_new_guarantees = yearly["guarantees"]["new"]

        # === EXTRACT DECEMBER'S CARRIED FORWARD ===
        december_entry = next((m for m in monthly_summary if "December" in m["month"]), None)
        year_end_balances = {"savings": {}, "ventures": {}, "loans": {}}
        if december_entry:
            for item in december_entry["savings"]["by_type"]:
                year_end_balances["savings"][item["type"]] = item["balance_carried_forward"]
            for item in december_entry["ventures"]["by_type"]:
                year_end_balances["ventures"][item["venture_type"]] = item["balance_carried_forward"]
            for item in december_entry["loans"]["by_type"]:
                year_end_balances["loans"][item["loan_type"]] = item["balance_carried_forward"]
        else:
            for name in all_savings_types.keys():
                year_end_balances["savings"][name] = float(running["savings"][name])
            for name in all_venture_types.keys():
                year_end_balances["ventures"][name] = float(running["venture_net"][name])
            for name in all_loan_types.keys():
                year_end_balances["loans"][name] = float(running["loan_out"][name])

        # === CHART OF ACCOUNTS ===
        chart_of_accounts = {
            "total_savings": float(total_savings),
            "total_ventures": float(total_ventures_net),
            "total_loans": float(total_loan_out),
            "total_savings_deposits": float(total_savings),
            "total_ventures_deposits": float(total_vent_dep),
            "total_ventures_payments": float(total_vent_pay),
            "total_loans_disbursed": float(total_loan_disb),
            "total_loans_repaid": float(total_loan_rep),
            "total_fee_income": float(total_fee_income),
            "total_member_contributions": float(total_member_contributions),
            "total_savings_by_type": [
                {"type": name, "amount": float(yearly["savings"].get(name, Decimal("0")))}
                for name in all_savings_types.keys()
            ],
            "total_ventures_by_type": [
                {
                    "venture_type": name,
                    "net_amount": float(
                        yearly["vent_dep"].get(name, Decimal("0")) - yearly["vent_pay"].get(name, Decimal("0"))
                    ),
                }
                for name in all_venture_types.keys()
            ],
            "total_loans_by_type": [
                {
                    "loan_type": name,
                    "total_outstanding_amount": float(running["loan_out"].get(name, Decimal("0"))),
                }
                for name in all_loan_types.keys()
            ],
        }

        # === FINAL RESPONSE ===
        return Response(
            {
                "year": year,
                "summary": {
                    "total_savings": float(total_savings),
                    "total_venture_deposits": float(total_vent_dep),
                    "total_venture_payments": float(total_vent_pay),
                    "total_ventures_net": float(total_ventures_net),
                    "total_loans_disbursed": float(total_loan_disb),
                    "total_loans_repaid": float(total_loan_rep),
                    "total_interest_charged": float(total_loan_int),
                    "total_loans_outstanding": float(total_loan_out),
                    "total_fee_income": float(total_fee_income),
                    "total_member_contributions": float(total_member_contributions),
                    "total_guaranteed_active": float(total_active_guarantees),
                    "total_new_guarantees": float(total_new_guarantees),
                    "total_fees_outstanding": float(total_fees_outstanding),
                    "year_end_balances": year_end_balances,
                },
                "monthly_summary": monthly_summary,
                "chart_of_accounts": chart_of_accounts,
            },
            status=status.HTTP_200_OK,
        )

# ------------------------------------------------------------------
# Async PDF Generator (Playwright)
# ------------------------------------------------------------------
async def generate_pdf_async(html_content: str, logo_url: str, landscape: bool = True):
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.add_init_script(f"window.LOGO_URL = '{logo_url}';")
        await page.set_content(html_content, wait_until="networkidle")
        pdf_bytes = await page.pdf(
            format="A4",
            landscape=landscape,
            print_background=True,
            margin={"top": "1cm", "bottom": "1cm", "left": "1cm", "right": "1cm"},
        )
        await browser.close()
        return pdf_bytes


class MemberYearlySummaryPDFView(APIView):
    """
    Download member yearly financial summary as PDF using Playwright.
    """
    def get(self, request, member_no):
        year = int(request.query_params.get("year", datetime.now().year))
        member = get_object_or_404(User, member_no=member_no, is_member=True)

        # Reuse JSON view data
        json_view = MemberYearlySummaryView()
        json_view.request = request
        data = json_view.get(request, member_no).data

        # Prep Types & Rows
        savings_types = sorted(list({s["type"] for m in data["monthly_summary"] for s in m["savings"]["by_type"]}))
        venture_types = sorted(list({v["venture_type"] for m in data["monthly_summary"] for v in m["ventures"]["by_type"]}))
        loan_types = sorted(list({l["loan_type"] for m in data["monthly_summary"] for l in m["loans"]["by_type"]}))
        fee_types = sorted(list({f["type"] for m in data["monthly_summary"] for f in m["fees"]["by_type"]}))

        table_rows = []
        for m in data["monthly_summary"]:
            row = {
                "month": m["month"],
                "savings": [],
                "ventures": [],
                "loans": [],
                "fees": [],
                "total_guarantees": m["guarantees"]["new_guarantees"]
            }
            # Savings mapping
            s_map = {item["type"]: item for item in m["savings"]["by_type"]}
            for t in savings_types:
                item = s_map.get(t)
                row["savings"].append({
                    "dep": item["amount"] if item else 0,
                    "bal": item["balance_carried_forward"] if item else 0
                })
            # Ventures mapping
            v_map = {item["venture_type"]: item for item in m["ventures"]["by_type"]}
            for t in venture_types:
                item = v_map.get(t)
                row["ventures"].append({
                    "dep": item["total_venture_deposits"] if item else 0,
                    "pay": item["total_venture_payments"] if item else 0,
                    "bal": item["balance_carried_forward"] if item else 0
                })
            # Loans mapping
            l_map = {item["loan_type"]: item for item in m["loans"]["by_type"]}
            for t in loan_types:
                item = l_map.get(t)
                row["loans"].append({
                    "disb": item["total_amount_disbursed"] if item else 0,
                    "rep": item["total_amount_repaid"] if item else 0,
                    "int": item["total_interest_charged"] if item else 0,
                    "out": item["total_amount_outstanding"] if item else 0
                })
            # Fees mapping
            f_map = {item["fee_type"]: item for item in m["fees"]["by_type"]}
            for t in fee_types:
                item = f_map.get(t)
                row["fees"].append({
                    "amt": item["total_amount_paid"] if item else 0,
                    "bal": item["total_amount_outstanding"] if item else 0
                })
            table_rows.append(row)

        logo_url = "https://res.cloudinary.com/dhw8kulj3/image/upload/v1762838274/logoNoBg_umwk2o.png"
        html_string = render_to_string(
            "reports/yearly_summary_pdf.html",
            {
                "data": data,
                "member": member,
                "year": year,
                "logo_url": logo_url,
                "generated_at": datetime.now().strftime("%d %B %Y, %I:%M %p"),
                "savings_types": savings_types,
                "venture_types": venture_types,
                "loan_types": loan_types,
                "fee_types": fee_types,
                "table_rows": table_rows,
                "total_active_guarantees": data["summary"]["total_guaranteed_active"] if "total_guaranteed_active" in data["summary"] else 0,
                "chart_of_accounts": data["chart_of_accounts"]
            },
        )

        try:
            pdf_bytes = asyncio.run(generate_pdf_async(html_string, logo_url, landscape=True))
        except Exception as e:
            logger.error(f"PDF generation failed for {member_no}: {e}")
            return Response({"error": "Failed to generate PDF"}, status=500)

        response = HttpResponse(pdf_bytes, content_type="application/pdf")
        response["Content-Disposition"] = f'attachment; filename="{member_no}_Summary_{year}.pdf"'
        return response


# =================================================================================================
# SACCO FINANCIAL REPORTING
# =================================================================================================

class SACCOSummaryView(APIView):
    """
    Detailed annual financial summary for the entire SACCO.
    Matches the depth of the Member summary but aggregated SACCO-wide.
    """
    def get(self, request):
        year = int(request.query_params.get("year", datetime.now().year))
        
        # === PRELOAD ALL TYPES ===
        all_savings_types = {t.name: t for t in SavingsType.objects.all()}
        all_venture_types = {t.name: t for t in VentureType.objects.all()}
        all_loan_types = {t.name: t for t in LoanType.objects.all()}
        all_fee_types = {t.name: t for t in FeeType.objects.all()}

        # === 1. FETCH PRIOR YEAR ENDING BALANCES (for B/F in January) ===
        prior_year = year - 1
        prior_balances = {
            "savings": {name: Decimal("0") for name in all_savings_types.keys()},
            "venture_net": {name: Decimal("0") for name in all_venture_types.keys()},
            "loan_out": {name: Decimal("0") for name in all_loan_types.keys()},
            "fee_out": {name: Decimal("0") for name in all_fee_types.keys()},
        }

        if prior_year >= 2020:
            # --- SAVINGS ---
            prior_savings = (
                SavingsDeposit.objects.filter(created_at__year__lt=year)
                .values("savings_account__account_type__name")
                .annotate(total=Sum("amount"))
            )
            for item in prior_savings:
                name = item["savings_account__account_type__name"]
                if name in prior_balances["savings"]:
                    prior_balances["savings"][name] = Decimal(str(item["total"]))

            # --- VENTURES ---
            prior_vent_deps = (
                VentureDeposit.objects.filter(created_at__year__lt=year)
                .values("venture_account__venture_type__name")
                .annotate(total=Sum("amount"))
            )
            prior_vent_pays = (
                VenturePayment.objects.filter(created_at__year__lt=year)
                .values("venture_account__venture_type__name")
                .annotate(total=Sum("amount"))
            )
            dep_map = {x["venture_account__venture_type__name"]: Decimal(str(x["total"])) for x in prior_vent_deps}
            pay_map = {x["venture_account__venture_type__name"]: Decimal(str(x["total"])) for x in prior_vent_pays}
            for name in all_venture_types.keys():
                prior_balances["venture_net"][name] = dep_map.get(name, Decimal("0")) - pay_map.get(name, Decimal("0"))

            # --- LOANS ---
            prior_disb = (
                LoanDisbursement.objects.filter(created_at__year__lt=year, transaction_status="Completed")
                .values("loan_account__loan_type__name")
                .annotate(total=Sum("amount"))
            )
            prior_rep = (
                LoanRepayment.objects.filter(
                    created_at__year__lt=year,
                    transaction_status="Completed",
                    repayment_type__in=["Regular Repayment", "Early Settlement", "Partial Payment", "Individual Settlement"]
                )
                .values("loan_account__loan_type__name")
                .annotate(total=Sum("amount"))
            )
            disb_map = {x["loan_account__loan_type__name"]: Decimal(str(x["total"])) for x in prior_disb}
            rep_map = {x["loan_account__loan_type__name"]: Decimal(str(x["total"])) for x in prior_rep}
            for name in all_loan_types.keys():
                disb = disb_map.get(name, Decimal("0"))
                rep = rep_map.get(name, Decimal("0"))
                prior_balances["loan_out"][name] = max(disb - rep, Decimal("0"))

            # --- FEES ---
            prior_fee_pays_sacco = (
                FeePayment.objects.filter(
                    created_at__year__lt=year,
                )
                .values("member_fee__fee_type__name")
                .annotate(total=Sum("amount"))
            )
            fee_pay_map_sacco = {x["member_fee__fee_type__name"]: Decimal(str(x["total"])) for x in prior_fee_pays_sacco}
            for name, ftype in all_fee_types.items():
                mfees_for_type = MemberFee.objects.filter(fee_type=ftype)
                billed_prior = sum([f.amount for f in mfees_for_type if f.created_at.year < year])
                pay = fee_pay_map_sacco.get(name, Decimal("0"))
                prior_balances["fee_out"][name] = max(billed_prior - pay, Decimal("0"))

        # === 2. INITIALIZE RUNNING BALANCES WITH PRIOR YEAR ===
        running = {
            "savings": prior_balances["savings"].copy(),
            "venture_net": prior_balances["venture_net"].copy(),
            "loan_out": prior_balances["loan_out"].copy(),
            "fee_out": prior_balances["fee_out"].copy(),
        }

        # === YEARLY ACCUMULATORS ===
        yearly = {
            "savings": {name: Decimal("0") for name in all_savings_types.keys()},
            "vent_dep": {name: Decimal("0") for name in all_venture_types.keys()},
            "vent_pay": {name: Decimal("0") for name in all_venture_types.keys()},
            "loan_disb": {name: Decimal("0") for name in all_loan_types.keys()},
            "loan_rep": {name: Decimal("0") for name in all_loan_types.keys()},
            "loan_int": {name: Decimal("0") for name in all_loan_types.keys()},
            "fee_income": {name: Decimal("0") for name in all_fee_types.keys() if all_fee_types[name].is_income},
            "member_contributions": {name: Decimal("0") for name in all_fee_types.keys() if not all_fee_types[name].is_income},
            "guarantees": {"new": Decimal("0")},
        }

        try:
            total_active_guarantees = GuarantorProfile.objects.aggregate(total=Sum('committed_guarantee_amount'))['total'] or Decimal('0')
        except:
            total_active_guarantees = Decimal("0")

        try:
            total_fees_outstanding = sum(f.remaining_balance for f in MemberFee.objects.all())
        except Exception:
            total_fees_outstanding = Decimal("0")

        # === FEES ===
        total_fees = FeePayment.objects.filter(
            created_at__year=year
        ).aggregate(total=Sum("amount"))["total"] or Decimal("0")

        # Helper to group by month
        def get_monthly_summary_data(queryset, date_field="created_at"):
            return (
                queryset
                .filter(created_at__year=year)
                .annotate(month=TruncMonth(date_field))
                .values("month")
                .annotate(total=Sum("amount"))
                .order_by("month")
            )

        # 1. Savings
        savings_qs = SavingsDeposit.objects.filter(created_at__year=year, transaction_status="Completed").annotate(month=TruncMonth("created_at")).values("month", "savings_account__account_type__name").annotate(total=Sum("amount"))
        savings_by_month = {}  # type: dict[int, dict[str, Decimal]]
        for item in savings_qs:
            m = item["month"].month
            name = item["savings_account__account_type__name"]
            if m not in savings_by_month:
                savings_by_month[m] = {}
            m_s = savings_by_month[m]
            m_s[name] = Decimal(str(item["total"]))  # type: ignore

        # 2. Ventures
        vent_dep_qs = VentureDeposit.objects.filter(created_at__year=year).annotate(month=TruncMonth("created_at")).values("month", "venture_account__venture_type__name").annotate(total=Sum("amount"))
        vent_pay_qs = VenturePayment.objects.filter(created_at__year=year, transaction_status="Completed").annotate(month=TruncMonth("created_at")).values("month", "venture_account__venture_type__name").annotate(total=Sum("amount"))
        
        vent_dep_by_month = {}  # type: dict[int, dict[str, Decimal]]
        for item in vent_dep_qs:
            m = item["month"].month
            name = item["venture_account__venture_type__name"]
            if m not in vent_dep_by_month:
                vent_dep_by_month[m] = {}
            m_vd = vent_dep_by_month[m]
            m_vd[name] = Decimal(str(item["total"]))  # type: ignore
        
        vent_pay_by_month = {}  # type: dict[int, dict[str, Decimal]]
        for item in vent_pay_qs:
            m = item["month"].month
            name = item["venture_account__venture_type__name"]
            if m not in vent_pay_by_month:
                vent_pay_by_month[m] = {}
            m_vp = vent_pay_by_month[m]
            m_vp[name] = Decimal(str(item["total"]))  # type: ignore

        # 3. Loans
        loan_disb_qs = LoanDisbursement.objects.filter(created_at__year=year, transaction_status="Completed").annotate(month=TruncMonth("created_at")).values("month", "loan_account__loan_type__name").annotate(total=Sum("amount"))
        loan_rep_qs = LoanRepayment.objects.filter(created_at__year=year, transaction_status="Completed").annotate(month=TruncMonth("created_at")).values("month", "loan_account__loan_type__name").annotate(total=Sum("amount"))
        loan_int_qs = TamarindLoanInterest.objects.filter(created_at__year=year).annotate(month=TruncMonth("created_at")).values("month", "loan_account__loan_type__name").annotate(total=Sum("amount"))

        loan_disb_by_month = {}  # type: dict[int, dict[str, Decimal]]
        for item in loan_disb_qs:
            m = item["month"].month
            name = item["loan_account__loan_type__name"]
            if m not in loan_disb_by_month:
                loan_disb_by_month[m] = {}
            m_ld = loan_disb_by_month[m]
            m_ld[name] = Decimal(str(item["total"]))  # type: ignore

        loan_rep_by_month = {}  # type: dict[int, dict[str, Decimal]]
        for item in loan_rep_qs:
            m = item["month"].month
            name = item["loan_account__loan_type__name"]
            if m not in loan_rep_by_month:
                loan_rep_by_month[m] = {}
            m_lr = loan_rep_by_month[m]
            m_lr[name] = Decimal(str(item["total"]))  # type: ignore
            
        loan_int_by_month = {}  # type: dict[int, dict[str, Decimal]]
        for item in loan_int_qs:
            m = item["month"].month
            name = item["loan_account__loan_type__name"]
            if m not in loan_int_by_month:
                loan_int_by_month[m] = {}
            m_li = loan_int_by_month[m]
            m_li[name] = Decimal(str(item["total"]))  # type: ignore

        # 4. Guarantees
        new_guarantees_qs = GuaranteeRequest.objects.filter(status="Accepted", created_at__year=year).annotate(month=TruncMonth("created_at")).values("month").annotate(total=Sum("guaranteed_amount"))
        guarantees_by_month = {}  # type: dict[int, Decimal]
        for item in new_guarantees_qs:
            guarantees_by_month[item["month"].month] = Decimal(str(item["total"]))

        # 5. Fees
        fees_qs = FeePayment.objects.filter(
            created_at__year=year
        ).annotate(
            month=TruncMonth("created_at")
        ).values("month", "member_fee__fee_type__name").annotate(total=Sum("amount"))

        fees_by_month = {}  # type: dict[int, dict[str, Decimal]]
        income_fees_by_month = {} # type: dict[int, Decimal]
        contributions_by_month = {} # type: dict[int, Decimal]

        for item in fees_qs:
            m = item["month"].month
            name = item["member_fee__fee_type__name"]
            amount = Decimal(str(item["total"]))
            is_income = all_fee_types[name].is_income
            
            if m not in fees_by_month:
                fees_by_month[m] = {}
            fees_by_month[m][name] = amount

            if is_income:
                income_fees_by_month[m] = income_fees_by_month.get(m, Decimal("0")) + amount
            else:
                contributions_by_month[m] = contributions_by_month.get(m, Decimal("0")) + amount

        monthly_summary = []

        # === 3. LOOP THROUGH EACH MONTH ===
        for month in range(1, 13):
            month_name = calendar.month_name[month]
            month_key = f"{month_name} {year}"

            # Savings
            m_savings = savings_by_month.get(month, {})
            enhanced_savings = []
            total_savings_month = Decimal("0")
            for name in all_savings_types.keys():
                amt = Decimal(str(m_savings.get(name, 0)))
                r_savings = running["savings"]
                brought = Decimal(str(r_savings.get(name, 0)))
                
                current_bal = brought + amt
                r_savings[name] = current_bal  # type: ignore
                total_savings_month += amt
                
                s_yearly = yearly["savings"]
                s_yearly[name] = s_yearly.get(name, Decimal("0")) + amt  # type: ignore
                
                enhanced_savings.append({
                    "type": name,
                    "amount": float(amt),
                    "total_deposits": float(amt),
                    "balance_brought_forward": float(brought),
                    "balance_carried_forward": float(current_bal),
                })

            # Ventures
            m_vent_dep = vent_dep_by_month.get(month, {})
            m_vent_pay = vent_pay_by_month.get(month, {})
            enhanced_ventures = []
            total_vent_dep_m = Decimal("0")
            total_vent_pay_m = Decimal("0")
            for name in all_venture_types.keys():
                d_amt = Decimal(str(m_vent_dep.get(name, 0)))
                p_amt = Decimal(str(m_vent_pay.get(name, 0)))
                r_vent = running["venture_net"]
                brought = Decimal(str(r_vent.get(name, 0)))
                
                net_change = d_amt - p_amt
                current_bal = brought + net_change
                r_vent[name] = current_bal  # type: ignore
                
                total_vent_dep_m += d_amt
                total_vent_pay_m += p_amt
                
                v_yearly_dep = yearly["vent_dep"]
                v_yearly_dep[name] = v_yearly_dep.get(name, Decimal("0")) + d_amt  # type: ignore
                v_yearly_pay = yearly["vent_pay"]
                v_yearly_pay[name] = v_yearly_pay.get(name, Decimal("0")) + p_amt  # type: ignore
                
                enhanced_ventures.append({
                    "venture_type": name,
                    "total_venture_deposits": float(d_amt),
                    "total_venture_payments": float(p_amt),
                    "balance_brought_forward": float(brought),
                    "balance_carried_forward": float(current_bal),
                })

            # Loans
            m_loan_disb = loan_disb_by_month.get(month, {})
            m_loan_rep = loan_rep_by_month.get(month, {})
            m_loan_int = loan_int_by_month.get(month, {})
            enhanced_loans = []
            total_loan_disb_m = Decimal("0")
            total_loan_rep_m = Decimal("0")
            total_loan_int_m = Decimal("0")
            for name in all_loan_types.keys():
                d_amt = Decimal(str(m_loan_disb.get(name, 0)))
                r_amt = Decimal(str(m_loan_rep.get(name, 0)))
                i_amt = Decimal(str(m_loan_int.get(name, 0)))
                r_loan = running["loan_out"]
                brought = Decimal(str(r_loan.get(name, 0)))
                
                net_change = d_amt - r_amt
                current_bal = brought + net_change
                r_loan[name] = current_bal  # type: ignore
                
                total_loan_disb_m += d_amt
                total_loan_rep_m += r_amt
                total_loan_int_m += i_amt
                
                ld_yearly = yearly["loan_disb"]
                ld_yearly[name] = ld_yearly.get(name, Decimal("0")) + d_amt  # type: ignore
                lr_yearly = yearly["loan_rep"]
                lr_yearly[name] = lr_yearly.get(name, Decimal("0")) + r_amt  # type: ignore
                li_yearly = yearly["loan_int"]
                li_yearly[name] = li_yearly.get(name, Decimal("0")) + i_amt  # type: ignore
                
                enhanced_loans.append({
                    "loan_type": name,
                    "total_amount_disbursed": float(d_amt),
                    "total_amount_repaid": float(r_amt),
                    "total_interest_charged": float(i_amt),
                    "total_amount_outstanding": float(current_bal),
                    "balance_brought_forward": float(brought),
                    "balance_carried_forward": float(current_bal),
                })

            # Guarantees
            g_amt = Decimal(str(guarantees_by_month.get(month, 0)))
            g_yearly = yearly["guarantees"]
            g_yearly["new"] = g_yearly.get("new", Decimal("0")) + g_amt

            # Fees
            m_fees = fees_by_month.get(month, {})
            enhanced_fees = []
            
            # if a fee was billed this month, add to running balance before subtracting payments
            for name, ftype in all_fee_types.items():
                mfees_for_type = MemberFee.objects.filter(fee_type=ftype)
                billed_month = sum([f.amount for f in mfees_for_type if f.created_at.year == year and f.created_at.month == month])
                running["fee_out"][name] = Decimal(str(running["fee_out"].get(name, 0))) + billed_month

            for name in all_fee_types.keys():
                amt = Decimal(str(m_fees.get(name, 0)))
                is_income = all_fee_types[name].is_income
                
                mfees_for_type = MemberFee.objects.filter(fee_type=all_fee_types[name])
                billed_month = sum([f.amount for f in mfees_for_type if f.created_at.year == year and f.created_at.month == month])
                
                r_fee = running["fee_out"]
                brought = Decimal(str(r_fee.get(name, 0))) - (billed_month - amt)
                r_fee[name] = max(Decimal(str(r_fee.get(name, 0))) - amt, Decimal("0"))
                
                total_expected = sum([f.amount for f in mfees_for_type])
                
                enhanced_fees.append({
                    "fee_type": name,
                    "total_expected": float(total_expected),
                    "total_amount_paid": float(amt),
                    "total_amount_outstanding": float(r_fee.get(name, 0)),
                    "balance_brought_forward": float(brought),
                    "balance_carried_forward": float(r_fee.get(name, 0)),
                    "is_income": is_income
                })
                
                if is_income:
                    yearly["fee_income"][name] += amt
                else:
                    yearly["member_contributions"][name] += amt
            
            income_month = income_fees_by_month.get(month, Decimal("0"))
            contributions_month = contributions_by_month.get(month, Decimal("0"))
                
            # The following block seems to be a remnant or a mistake in the provided instruction.
            # It's commented out to avoid syntax errors and logical inconsistencies.
            # enhanced_fees.append({
            #     "type": name,
            #     "amount": float(f_amt),
            # })

            monthly_summary.append({
                "month": month_name,
                "savings": {
                    "total_deposits": float(total_savings_month),
                    "total_balance": float(sum([Decimal(str(v)) for v in running["savings"].values()])),
                    "by_type": enhanced_savings,
                },
                "ventures": {
                    "venture_deposits": float(total_vent_dep_m),
                    "venture_payments": float(total_vent_pay_m),
                    "venture_balance": float(total_vent_dep_m - total_vent_pay_m),
                    "total_balance": float(sum([Decimal(str(v)) for v in running["venture_net"].values()])),
                    "by_type": enhanced_ventures,
                },
                "loans": {
                    "total_loans_disbursed": float(total_loan_disb_m),
                    "total_loans_repaid": float(total_loan_rep_m),
                    "total_interest_charged": float(total_loan_int_m),
                    "total_loans_outstanding": float(sum([Decimal(str(v)) for v in running["loan_out"].values()])),
                    "total_balance": float(sum([Decimal(str(v)) for v in running["loan_out"].values()])),
                    "by_type": enhanced_loans,
                },
                "guarantees": {
                    "new_guarantees": float(g_amt),
                    "transactions": [] 
                },
                "fees": {
                    "fee_income": float(income_month),
                    "member_contributions": float(contributions_month),
                    "by_type": enhanced_fees,
                },
            })

        # === YEARLY TOTALS ===
        total_savings = sum(yearly["savings"].values())
        total_vent_dep = sum(yearly["vent_dep"].values())
        total_vent_pay = sum(yearly["vent_pay"].values())
        total_ventures_net = total_vent_dep - total_vent_pay
        total_loan_disb = sum(yearly["loan_disb"].values())
        total_loan_rep = sum(yearly["loan_rep"].values())
        total_loan_int = sum(yearly["loan_int"].values())
        total_loan_out = sum(running["loan_out"].values())
        total_fee_income = sum(yearly["fee_income"].values())
        total_member_contributions = sum(yearly["member_contributions"].values())
        total_new_guarantees = yearly["guarantees"]["new"]

        # Final Response
        return Response({
            "summary": {
                "total_savings": float(sum(running["savings"].values())),
                "total_venture_balance": float(sum(running["venture_net"].values())),
                "total_loan_outstanding": float(sum(running["loan_out"].values())),
                "total_fee_income": float(sum(yearly["fee_income"].values())),
                "total_member_contributions": float(sum(yearly["member_contributions"].values())),
                "total_fees_outstanding": float(MemberFee.objects.aggregate(total=Sum("remaining_balance"))["total"] or 0),
                "total_guaranteed_active": float(total_active_guarantees),
            },
            "yearly_accumulators": {
                "savings": {k: float(v) for k, v in yearly["savings"].items()},
                "venture_deposits": {k: float(v) for k, v in yearly["vent_dep"].items()},
                "venture_payments": {k: float(v) for k, v in yearly["vent_pay"].items()},
                "loan_disbursements": {k: float(v) for k, v in yearly["loan_disb"].items()},
                "loan_repayments": {k: float(v) for k, v in yearly["loan_rep"].items()},
                "loan_interest": {k: float(v) for k, v in yearly["loan_int"].items()},
                "fee_income": {k: float(v) for k, v in yearly["fee_income"].items()},
                "member_contributions": {k: float(v) for k, v in yearly["member_contributions"].items()},
                "guarantees": {k: float(v) for k, v in yearly["guarantees"].items()},
            },
            "monthly_summary": monthly_summary
        }, status=status.HTTP_200_OK)


class SACCOSummaryPDFView(APIView):
    """
    Download SACCO yearly financial summary as PDF.
    """
    def get(self, request):
        year = int(request.query_params.get("year", datetime.now().year))
        
        # Reuse JSON view
        json_view = SACCOSummaryView()
        data = json_view.get(request).data

        savings_types = sorted(list({s["type"] for m in data["monthly_summary"] for s in m["savings"]["by_type"]}))
        venture_types = sorted(list({v["venture_type"] for m in data["monthly_summary"] for v in m["ventures"]["by_type"]}))
        loan_types = sorted(list({l["loan_type"] for m in data["monthly_summary"] for l in m["loans"]["by_type"]}))
        fee_types = sorted(list({f["fee_type"] for m in data["monthly_summary"] for f in m["fees"]["by_type"]}))

        table_rows = []
        for m in data["monthly_summary"]:
            row = {
                "month": m["month"],
                "savings": [],
                "ventures": [],
                "loans": [],
                "fees": [],
                "total_guarantees": m["guarantees"]["new_guarantees"]
            }
            s_map = {item["type"]: item for item in m["savings"]["by_type"]}
            for t in savings_types:
                item = s_map.get(t)
                row["savings"].append({
                    "dep": item["amount"] if item else 0,
                    "bal": item["balance_carried_forward"] if item else 0
                })
            v_map = {item["venture_type"]: item for item in m["ventures"]["by_type"]}
            for t in venture_types:
                item = v_map.get(t)
                row["ventures"].append({
                    "dep": item["total_venture_deposits"] if item else 0,
                    "pay": item["total_venture_payments"] if item else 0,
                    "bal": item["balance_carried_forward"] if item else 0
                })
            l_map = {item["loan_type"]: item for item in m["loans"]["by_type"]}
            for t in loan_types:
                item = l_map.get(t)
                row["loans"].append({
                    "disb": item["total_amount_disbursed"] if item else 0,
                    "rep": item["total_amount_repaid"] if item else 0,
                    "int": item["total_interest_charged"] if item else 0,
                    "out": item["total_amount_outstanding"] if item else 0
                })
            f_map = {item["fee_type"]: item for item in m["fees"]["by_type"]}
            for t in fee_types:
                item = f_map.get(t)
                row["fees"].append({
                    "amt": item["total_amount_paid"] if item else 0,
                    "bal": item["total_amount_outstanding"] if item else 0
                })
            table_rows.append(row)

        logo_url = "https://res.cloudinary.com/dhw8kulj3/image/upload/v1762838274/logoNoBg_umwk2o.png"
        html_string = render_to_string(
            "reports/sacco_summary_pdf.html",
            {
                "data": data,
                "year": year,
                "logo_url": logo_url,
                "generated_at": datetime.now().strftime("%d %B %Y, %I:%M %p"),
                "savings_types": savings_types,
                "venture_types": venture_types,
                "loan_types": loan_types,
                "fee_types": fee_types,
                "table_rows": table_rows,
                "total_active_guarantees": data["summary"]["total_guaranteed_active"],
            }
        )
        
        try:
            # Full detail SACCO summary is better in landscape
            pdf_bytes = asyncio.run(generate_pdf_async(html_string, logo_url, landscape=True))
        except Exception as e:
            logger.error(f"SACCO PDF generation failed: {e}")
            return Response({"error": f"PDF generation failed"}, status=500)

        response = HttpResponse(pdf_bytes, content_type="application/pdf")
        filename = f"SACCO_Detailed_Summary_{year}.pdf"
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        return response


class CashbookView(APIView):
    """
    Chronological flow of funds (Cash/Bank account entries).
    """
    def get(self, request):
        # We focus on the Cash at Bank account (Code 1010)
        cash_acc = GLAccount.objects.get(code='1010')
        entries = JournalEntry.objects.filter(gl_account=cash_acc).order_by('transaction_date', 'created_at')
        
        results = []
        running_balance = Decimal('0')
        
        for entry in entries:
            running_balance += (entry.debit - entry.credit)
            results.append({
                'date': entry.transaction_date,
                'description': entry.description,
                'debit': float(entry.debit),
                'credit': float(entry.credit),
                'balance': float(running_balance),
                'reference': entry.reference_id,
                'source': entry.source_model
            })
            
        return Response(results, status=status.HTTP_200_OK)
class MemberStatementView(APIView):
    """
    Unified chronological statement of all transactions for a specific member.
    """
    def get(self, request, member_no):
        member = get_object_or_404(User, member_no=member_no, is_member=True)
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')

        # 1. Fetch all transaction types
        savings_deps = SavingsDeposit.objects.filter(savings_account__member=member, transaction_status="Completed")
        savings_with = SavingsWithdrawal.objects.filter(savings_account__member=member, transaction_status="Completed")
        venture_deps = VentureDeposit.objects.filter(venture_account__member=member)
        venture_pays = VenturePayment.objects.filter(venture_account__member=member)
        loan_disb = LoanDisbursement.objects.filter(loan_account__member=member, transaction_status="Completed")
        loan_rep = LoanRepayment.objects.filter(loan_account__member=member, transaction_status="Completed")
        loan_int = TamarindLoanInterest.objects.filter(loan_account__member=member)
        fee_pays = FeePayment.objects.filter(member_fee__member=member, transaction_status="Completed")

        # 2. Filter by date if provided
        if start_date:
            savings_deps = savings_deps.filter(created_at__date__gte=start_date)
            savings_with = savings_with.filter(created_at__date__gte=start_date)
            venture_deps = venture_deps.filter(created_at__date__gte=start_date)
            venture_pays = venture_pays.filter(created_at__date__gte=start_date)
            loan_disb = loan_disb.filter(created_at__date__gte=start_date)
            loan_rep = loan_rep.filter(created_at__date__gte=start_date)
            loan_int = loan_int.filter(created_at__date__gte=start_date)
            fee_pays = fee_pays.filter(created_at__date__gte=start_date)

        if end_date:
            savings_deps = savings_deps.filter(created_at__date__lte=end_date)
            savings_with = savings_with.filter(created_at__date__lte=end_date)
            venture_deps = venture_deps.filter(created_at__date__lte=end_date)
            venture_pays = venture_pays.filter(created_at__date__lte=end_date)
            loan_disb = loan_disb.filter(created_at__date__lte=end_date)
            loan_rep = loan_rep.filter(created_at__date__lte=end_date)
            loan_int = loan_int.filter(created_at__date__lte=end_date)
            fee_pays = fee_pays.filter(created_at__date__lte=end_date)

        # 3. Combine and sort
        all_transactions = sorted(
            list(savings_deps) + list(savings_with) + list(venture_deps) + 
            list(venture_pays) + list(loan_disb) + list(loan_rep) + 
            list(loan_int) + list(fee_pays),
            key=lambda x: x.created_at,
            reverse=True
        )

        # 4. Serialize
        serializer = MemberTransactionSerializer(all_transactions, many=True)
        return Response(serializer.data)
