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
from django.db.models import Sum, Case, When, DecimalField, F
from django.db.models.functions import ExtractMonth, ExtractYear
from rest_framework.views import APIView


from savings.models import SavingsType
from ventures.models import VentureType
from transactions.serializers import (
    AccountSerializer,
    MonthlySummarySerializer,
    BulkUploadSerializer
)
from transactions.models import DownloadLog, BulkTransactionLog
from accounts.permissions import IsSystemAdminOrReadOnly
from loantypes.models import LoanType
from savingsdeposits.models import SavingsDeposit
from venturepayments.models import VenturePayment
from venturedeposits.models import VentureDeposit
from ventures.models import VentureAccount
from loans.models import LoanAccount
from loanrepayments.models import LoanRepayment
from loanintereststamarind.models import TamarindLoanInterest
from loandisbursements.models import LoanDisbursement
from savings.models import SavingsAccount


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

        # Validate: At least one valid account column
        valid_pairs = 0
        for t in savings_types + venture_types + loan_types:
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
    """

    def get(self, request, member_no):
        year = int(request.query_params.get("year", datetime.now().year))
        member = get_object_or_404(User, member_no=member_no, is_member=True)

        # === PRELOAD ALL TYPES ===
        all_savings_types = {t.name: t for t in SavingsType.objects.all()}
        all_venture_types = {t.name: t for t in VentureType.objects.all()}
        all_loan_types = {t.name: t for t in LoanType.objects.all()}

        # === 1. FETCH PRIOR YEAR ENDING BALANCES (for B/F in January) ===
        prior_year = year - 1
        prior_balances = {
            "savings": {name: Decimal("0") for name in all_savings_types.keys()},
            "venture_net": {name: Decimal("0") for name in all_venture_types.keys()},
            "loan_out": {name: Decimal("0") for name in all_loan_types.keys()},
        }

        if prior_year >= 2020:  # adjust as needed
            # --- SAVINGS: Total deposits in prior year ---
            prior_savings = (
                SavingsDeposit.objects.filter(
                    savings_account__member=member,
                    created_at__year=prior_year,
                )
                .values("savings_account__account_type__name")
                .annotate(total=Sum("amount"))
            )
            for item in prior_savings:
                name = item["savings_account__account_type__name"]
                if name in prior_balances["savings"]:
                    prior_balances["savings"][name] = Decimal(str(item["total"]))

            # --- VENTURES: Net (dep - pay) in prior year ---
            prior_vent_deps = (
                VentureDeposit.objects.filter(
                    venture_account__member=member,
                    created_at__year=prior_year,
                )
                .values("venture_account__venture_type__name")
                .annotate(total=Sum("amount"))
            )
            prior_vent_pays = (
                VenturePayment.objects.filter(
                    venture_account__member=member,
                    created_at__year=prior_year,
                )
                .values("venture_account__venture_type__name")
                .annotate(total=Sum("amount"))
            )

            dep_map = {
                x["venture_account__venture_type__name"]: Decimal(str(x["total"]))
                for x in prior_vent_deps
            }
            pay_map = {
                x["venture_account__venture_type__name"]: Decimal(str(x["total"]))
                for x in prior_vent_pays
            }

            for name in all_venture_types.keys():
                dep = dep_map.get(name, Decimal("0"))
                pay = pay_map.get(name, Decimal("0"))
                prior_balances["venture_net"][name] = dep - pay

            # --- LOANS: Outstanding at end of prior year ---
            prior_disb = (
                LoanDisbursement.objects.filter(
                    loan_account__member=member,
                    created_at__year=prior_year,
                    transaction_status="Completed",
                )
                .values("loan_account__loan_type__name")
                .annotate(total=Sum("amount"))
            )
            prior_rep = (
                LoanRepayment.objects.filter(
                    loan_account__member=member,
                    created_at__year=prior_year,
                    transaction_status="Completed",
                    repayment_type__in=[
                        "Regular Repayment",
                        "Early Settlement",
                        "Partial Payment",
                        "Individual Settlement",
                    ],
                )
                .values("loan_account__loan_type__name")
                .annotate(total=Sum("amount"))
            )

            disb_map = {
                x["loan_account__loan_type__name"]: Decimal(str(x["total"]))
                for x in prior_disb
            }
            rep_map = {
                x["loan_account__loan_type__name"]: Decimal(str(x["total"]))
                for x in prior_rep
            }

            for name in all_loan_types.keys():
                disb = disb_map.get(name, Decimal("0"))
                rep = rep_map.get(name, Decimal("0"))
                prior_balances["loan_out"][name] = max(disb - rep, Decimal("0"))

        # === 2. INITIALIZE RUNNING BALANCES WITH PRIOR YEAR ===
        running = {
            "savings": prior_balances["savings"].copy(),
            "venture_net": prior_balances["venture_net"].copy(),
            "loan_out": prior_balances["loan_out"].copy(),
        }

        # === YEARLY ACCUMULATORS ===
        yearly = {
            "savings": defaultdict(Decimal),
            "vent_dep": defaultdict(Decimal),
            "vent_pay": defaultdict(Decimal),
            "loan_disb": defaultdict(Decimal),
            "loan_rep": defaultdict(Decimal),
            "loan_int": defaultdict(Decimal),
        }

        monthly_summary = []

        # === 3. LOOP THROUGH EACH MONTH ===
        for month in range(1, 13):
            month_name = calendar.month_name[month]
            month_key = f"{month_name} {year}"

            # === SAVINGS ===
            savings_deps = SavingsDeposit.objects.filter(
                savings_account__member=member,
                created_at__year=year,
                created_at__month=month,
            ).select_related("savings_account__account_type")

            savings_by_type = defaultdict(
                lambda: {"total": Decimal("0"), "deposits": []}
            )
            for dep in savings_deps:
                stype = dep.savings_account.account_type.name
                amount = Decimal(str(dep.amount))
                savings_by_type[stype]["total"] += amount
                savings_by_type[stype]["deposits"].append(
                    {"type": stype, "amount": float(amount)}
                )
                yearly["savings"][stype] += amount

            # === VENTURES ===
            vent_deps = VentureDeposit.objects.filter(
                venture_account__member=member,
                created_at__year=year,
                created_at__month=month,
            ).select_related("venture_account__venture_type")

            vent_pays = VenturePayment.objects.filter(
                venture_account__member=member,
                created_at__year=year,
                created_at__month=month,
            ).select_related("venture_account__venture_type")

            vent_by_type = defaultdict(lambda: {"deposits": [], "payments": []})
            for dep in vent_deps:
                vtype = dep.venture_account.venture_type.name
                amount = Decimal(str(dep.amount))
                vent_by_type[vtype]["deposits"].append(
                    {"venture_type": vtype, "amount": float(amount)}
                )
                yearly["vent_dep"][vtype] += amount

            for pay in vent_pays:
                vtype = pay.venture_account.venture_type.name
                amount = Decimal(str(pay.amount))
                vent_by_type[vtype]["payments"].append(
                    {"venture_type": vtype, "amount": float(amount)}
                )
                yearly["vent_pay"][vtype] += amount

            # === LOANS ===
            disbursements = LoanDisbursement.objects.filter(
                loan_account__member=member,
                created_at__year=year,
                created_at__month=month,
                transaction_status="Completed",
            ).select_related("loan_account__loan_type")

            repayments = LoanRepayment.objects.filter(
                loan_account__member=member,
                created_at__year=year,
                created_at__month=month,
                transaction_status="Completed",
            ).select_related("loan_account__loan_type")

            interests = TamarindLoanInterest.objects.filter(
                loan_account__member=member,
                created_at__year=year,
                created_at__month=month,
            ).select_related("loan_account__loan_type")

            loan_by_type = defaultdict(
                lambda: {"disbursed": [], "repaid": [], "interest": []}
            )
            for d in disbursements:
                ltype = d.loan_account.loan_type.name
                amount = Decimal(str(d.amount))
                loan_by_type[ltype]["disbursed"].append(
                    {"loan_type": ltype, "amount": float(amount)}
                )
                yearly["loan_disb"][ltype] += amount

            for r in repayments:
                ltype = r.loan_account.loan_type.name
                amount = Decimal(str(r.amount))
                if r.repayment_type != "Interest Payment":
                    loan_by_type[ltype]["repaid"].append(
                        {"loan_type": ltype, "amount": float(amount)}
                    )
                    yearly["loan_rep"][ltype] += amount

            for i in interests:
                ltype = i.loan_account.loan_type.name
                amount = Decimal(str(i.amount))
                loan_by_type[ltype]["interest"].append(
                    {"loan_type": ltype, "amount": float(amount)}
                )
                yearly["loan_int"][ltype] += amount

            # === UPDATE RUNNING BALANCES ===
            for name, data in savings_by_type.items():
                running["savings"][name] += data["total"]

            for name, data in vent_by_type.items():
                dep = sum(d["amount"] for d in data["deposits"])
                pay = sum(p["amount"] for p in data["payments"])
                running["venture_net"][name] += Decimal(str(dep)) - Decimal(str(pay))

            for name, data in loan_by_type.items():
                disb = sum(d["amount"] for d in data["disbursed"])
                rep = sum(r["amount"] for r in data["repaid"])
                running["loan_out"][name] += Decimal(str(disb)) - Decimal(str(rep))

            # === BUILD MONTHLY SUMMARY WITH B/F & C/F ===
            savings_list = []
            for name in all_savings_types.keys():
                monthly_total = savings_by_type.get(name, {"total": Decimal("0")})[
                    "total"
                ]
                brought_forward = running["savings"][name] - monthly_total
                savings_list.append(
                    {
                        "type": name,
                        "amount": float(monthly_total),
                        "deposits": savings_by_type.get(name, {"deposits": []})[
                            "deposits"
                        ],
                        "balance_brought_forward": float(brought_forward),
                        "balance_carried_forward": float(running["savings"][name]),
                    }
                )

            ventures_list = []
            for name in all_venture_types.keys():
                dep_list = vent_by_type.get(name, {"deposits": []})["deposits"]
                pay_list = vent_by_type.get(name, {"payments": []})["payments"]
                dep = sum(d["amount"] for d in dep_list)
                pay = sum(p["amount"] for p in pay_list)
                net_month = dep - pay
                brought_forward = running["venture_net"][name] - Decimal(str(net_month))
                ventures_list.append(
                    {
                        "venture_type": name,
                        "venture_deposits": dep_list,
                        "venture_payments": pay_list,
                        "balance_brought_forward": float(brought_forward),
                        "balance_carried_forward": float(running["venture_net"][name]),
                    }
                )

            loans_list = []
            for name in all_loan_types.keys():
                disb_list = loan_by_type.get(name, {"disbursed": []})["disbursed"]
                rep_list = loan_by_type.get(name, {"repaid": []})["repaid"]
                int_list = loan_by_type.get(name, {"interest": []})["interest"]
                disb = sum(d["amount"] for d in disb_list)
                rep = sum(r["amount"] for r in rep_list)
                net_month = disb - rep
                brought_forward = running["loan_out"][name] - Decimal(str(net_month))
                loans_list.append(
                    {
                        "loan_type": name,
                        "total_amount_disbursed": disb_list,
                        "total_amount_repaid": rep_list,
                        "total_interest_charged": int_list,
                        "total_amount_outstanding": float(running["loan_out"][name]),
                        "balance_brought_forward": float(brought_forward),
                        "balance_carried_forward": float(running["loan_out"][name]),
                    }
                )

            # === APPEND MONTH ===
            monthly_summary.append(
                {
                    "month": month_key,
                    "savings": {
                        "by_type": savings_list,
                    },
                    "ventures": {
                        "by_type": ventures_list,
                    },
                    "loans": {
                        "by_type": loans_list,
                    },
                }
            )

        # === YEARLY TOTALS ===
        total_savings = sum(yearly["savings"].values())
        total_vent_dep = sum(yearly["vent_dep"].values())
        total_vent_pay = sum(yearly["vent_pay"].values())
        total_ventures_net = total_vent_dep - total_vent_pay
        total_loan_disb = sum(yearly["loan_disb"].values())
        total_loan_rep = sum(yearly["loan_rep"].values())
        total_loan_int = sum(yearly["loan_int"].values())

        # Final year-end outstanding
        final_cum_out = {}
        for name in all_loan_types.keys():
            disb = yearly["loan_disb"].get(name, Decimal("0"))
            rep = yearly["loan_rep"].get(name, Decimal("0"))
            final_cum_out[name] = max(disb - rep, Decimal("0"))
        total_loan_out = sum(final_cum_out.values())

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
            "total_savings_by_type": [
                {
                    "type": name,
                    "amount": float(yearly["savings"].get(name, Decimal("0"))),
                }
                for name in all_savings_types.keys()
            ],
            "total_ventures_by_type": [
                {
                    "venture_type": name,
                    "net_amount": float(
                        yearly["vent_dep"].get(name, Decimal("0"))
                        - yearly["vent_pay"].get(name, Decimal("0"))
                    ),
                }
                for name in all_venture_types.keys()
            ],
            "total_loans_by_type": [
                {
                    "loan_type": name,
                    "total_outstanding_amount": float(
                        final_cum_out.get(name, Decimal("0"))
                    ),
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
                },
                "monthly_summary": monthly_summary,
                "chart_of_accounts": chart_of_accounts,
            },
            status=status.HTTP_200_OK,
        )


# =====================================================================
# PDF GENERATION
# =====================================================================


# ------------------------------------------------------------------
# Async PDF Generator (Playwright)
# ------------------------------------------------------------------
async def generate_pdf(html_content: str, logo_url: str):
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        # Inject logo URL into page context
        await page.add_init_script(f"window.LOGO_URL = '{logo_url}';")

        # Set full HTML
        await page.set_content(html_content, wait_until="networkidle")

        # Generate PDF with header/footer
        pdf_bytes = await page.pdf(
            format="A4",
            print_background=True,
            margin={"top": "1.2cm", "bottom": "1.2cm", "left": "1cm", "right": "1cm"},
            display_header_footer=True,
            header_template="""
                <div style="font-size:10px; text-align:center; width:100%; padding:8px 0; border-bottom:1px solid #eee;">
                    <strong>Wananchi Mali SACCO</strong>
                </div>
            """,
            footer_template="""
                <div style="font-size:9px; text-align:center; width:100%; padding:5px 0; border-top:1px solid #eee; color:#666;">
                    Page <span class="pageNumber"></span> of <span class="totalPages"></span> 
                    | Generated on {{ generated_at }}
                </div>
            """.replace(
                "{{ generated_at }}", datetime.now().strftime("%d %B %Y")
            ),
        )
        await browser.close()
        return pdf_bytes


class MemberYearlySummaryPDFView(APIView):
    """
    Download member yearly financial summary as PDF.
    Uses Cloudinary logo: https://res.cloudinary.com/dhw8kulj3/image/upload/v1762838274/logoNoBg_umwk2o.png
    """

    def get(self, request, member_no):
        year = int(request.query_params.get("year", datetime.now().year))

        try:
            member = User.objects.get(member_no=member_no, is_member=True)
        except User.DoesNotExist:
            return Response({"error": "Member not found"}, status=404)

        # Reuse JSON view data
        from .views import MemberYearlySummaryView

        json_view = MemberYearlySummaryView()
        json_view.request = request
        data = json_view.get(request, member_no).data

        # Cloudinary logo URL
        logo_url = "https://res.cloudinary.com/dhw8kulj3/image/upload/v1762838274/logoNoBg_umwk2o.png"

        # Render HTML with logo
        html_string = render_to_string(
            "reports/yearly_summary_pdf.html",
            {
                "data": data,
                "member": member,
                "year": year,
                "logo_url": logo_url,
                "generated_at": datetime.now().strftime("%d %B %Y, %I:%M %p"),
            },
        )

        # Generate PDF
        try:
            pdf_bytes = asyncio.run(generate_pdf(html_string, logo_url))
        except Exception as e:
            logger.error(f"PDF generation failed for {member_no}: {e}")
            return Response({"error": "Failed to generate PDF"}, status=500)

        # Return download
        response = HttpResponse(pdf_bytes, content_type="application/pdf")
        response["Content-Disposition"] = (
            f'attachment; filename="{member_no}_Summary_{year}.pdf"'
        )
        return response
