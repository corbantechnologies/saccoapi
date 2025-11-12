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
    Returns yearly + monthly financial summary with CORRECT month-end loan balances.
    """

    def get(self, request, member_no):
        year = int(request.query_params.get("year", datetime.now().year))
        member = get_object_or_404(User, member_no=member_no, is_member=True)

        # Pre-load all types as dict: {name: model}
        all_savings_types = {t.name: t for t in SavingsType.objects.all()}
        all_venture_types = {t.name: t for t in VentureType.objects.all()}
        all_loan_types = {t.name: t for t in LoanType.objects.all()}

        # Year-level accumulators
        yearly = {
            "savings": defaultdict(Decimal),
            "vent_dep": defaultdict(Decimal),
            "vent_pay": defaultdict(Decimal),
            "loan_disb": defaultdict(Decimal),
            "loan_rep": defaultdict(Decimal),
            "loan_int": defaultdict(Decimal),
        }

        monthly_summary = []

        # Loop through each month
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

            savings_list = []
            total_savings_month = Decimal("0")
            for name in all_savings_types.keys():  # Use .keys()
                data = savings_by_type.get(
                    name, {"total": Decimal("0"), "deposits": []}
                )
                savings_list.append(
                    {
                        "type": name,
                        "amount": float(data["total"]),
                        "deposits": data["deposits"],
                    }
                )
                total_savings_month += data["total"]

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
            month_vent_dep = Decimal("0")
            month_vent_pay = Decimal("0")

            for dep in vent_deps:
                vtype = dep.venture_account.venture_type.name
                amount = Decimal(str(dep.amount))
                vent_by_type[vtype]["deposits"].append(
                    {"venture_type": vtype, "amount": float(amount)}
                )
                month_vent_dep += amount
                yearly["vent_dep"][vtype] += amount

            for pay in vent_pays:
                vtype = pay.venture_account.venture_type.name
                amount = Decimal(str(pay.amount))
                vent_by_type[vtype]["payments"].append(
                    {"venture_type": vtype, "amount": float(amount)}
                )
                month_vent_pay += amount
                yearly["vent_pay"][vtype] += amount

            venture_balance = month_vent_dep - month_vent_pay

            ventures_list = []
            for name in all_venture_types.keys():  # Use .keys()
                data = vent_by_type.get(name, {"deposits": [], "payments": []})
                ventures_list.append(
                    {
                        "venture_type": name,
                        "venture_deposits": data["deposits"],
                        "venture_payments": data["payments"],
                    }
                )

            # === LOANS: CORRECT MONTH-END BALANCE ===
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

            month_disb = Decimal("0")
            month_rep = Decimal("0")
            month_int = Decimal("0")

            loan_by_type = defaultdict(
                lambda: {"disbursed": [], "repaid": [], "interest": []}
            )

            for d in disbursements:
                ltype = d.loan_account.loan_type.name
                amount = Decimal(str(d.amount))
                loan_by_type[ltype]["disbursed"].append(
                    {"loan_type": ltype, "amount": float(amount)}
                )
                month_disb += amount
                yearly["loan_disb"][ltype] += amount

            for r in repayments:
                ltype = r.loan_account.loan_type.name
                amount = Decimal(str(r.amount))
                if r.repayment_type != "Interest Payment":
                    loan_by_type[ltype]["repaid"].append(
                        {"loan_type": ltype, "amount": float(amount)}
                    )
                    month_rep += amount
                    yearly["loan_rep"][ltype] += amount

            for i in interests:
                ltype = i.loan_account.loan_type.name
                amount = Decimal(str(i.amount))
                loan_by_type[ltype]["interest"].append(
                    {"loan_type": ltype, "amount": float(amount)}
                )
                month_int += amount
                yearly["loan_int"][ltype] += amount

            # CUMULATIVE UP TO THIS MONTH
            cum_disb = (
                LoanDisbursement.objects.filter(
                    loan_account__member=member,
                    created_at__year=year,
                    created_at__month__lte=month,
                    transaction_status="Completed",
                )
                .values("loan_account__loan_type__name")
                .annotate(total=Sum("amount"))
            )

            cum_rep = (
                LoanRepayment.objects.filter(
                    loan_account__member=member,
                    created_at__year=year,
                    created_at__month__lte=month,
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

            cumulative_outstanding_by_type = {}
            for type_name in all_loan_types.keys():  # FIXED
                disbursed = sum(
                    d["total"]
                    for d in cum_disb
                    if d["loan_account__loan_type__name"] == type_name
                ) or Decimal("0")
                repaid = sum(
                    r["total"]
                    for r in cum_rep
                    if r["loan_account__loan_type__name"] == type_name
                ) or Decimal("0")
                cumulative_outstanding_by_type[type_name] = max(
                    disbursed - repaid, Decimal("0")
                )

            # Build loans_list
            loans_list = []
            total_month_end_outstanding = Decimal("0")
            for type_name in all_loan_types.keys():  # FIXED
                data = loan_by_type.get(
                    type_name, {"disbursed": [], "repaid": [], "interest": []}
                )
                out = cumulative_outstanding_by_type.get(type_name, Decimal("0"))
                loans_list.append(
                    {
                        "loan_type": type_name,
                        "total_amount_outstanding": float(out),
                        "total_amount_disbursed": data["disbursed"],
                        "total_amount_repaid": data["repaid"],
                        "total_interest_charged": data["interest"],
                    }
                )
                total_month_end_outstanding += out

            # === Build Month ===
            monthly_summary.append(
                {
                    "month": month_key,
                    "savings": {
                        "total_savings": float(total_savings_month),
                        "total_savings_deposits": float(total_savings_month),
                        "by_type": savings_list,
                    },
                    "ventures": {
                        "venture_deposits": float(month_vent_dep),
                        "venture_payments": float(month_vent_pay),
                        "venture_balance": float(venture_balance),
                        "by_type": ventures_list,
                    },
                    "loans": {
                        "total_loans_disbursed": float(month_disb),
                        "total_loans_repaid": float(month_rep),
                        "total_interest_charged": float(month_int),
                        "total_loans_outstanding": float(total_month_end_outstanding),
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
        for type_name in all_loan_types.keys():  # FIXED
            disbursed = yearly["loan_disb"].get(type_name, Decimal("0"))
            repaid = yearly["loan_rep"].get(type_name, Decimal("0"))
            final_cum_out[type_name] = max(disbursed - repaid, Decimal("0"))
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
                    "loan_type": type_name,
                    "total_outstanding_amount": float(
                        final_cum_out.get(type_name, Decimal("0"))
                    ),
                }
                for type_name in all_loan_types.keys()  # FIXED
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
