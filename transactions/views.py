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
from django.db.models import Sum
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

        # === 1. FETCH PRIOR YEAR ENDING BALANCES (for B/F in January) ===
        prior_year = year - 1
        prior_balances = {
            "savings": {name: Decimal("0") for name in all_savings_types.keys()},
            "venture_net": {name: Decimal("0") for name in all_venture_types.keys()},
            "loan_out": {name: Decimal("0") for name in all_loan_types.keys()},
        }

        if prior_year >= 2020:
            # --- SAVINGS ---
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

            # --- VENTURES ---
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
            dep_map = {x["venture_account__venture_type__name"]: Decimal(str(x["total"])) for x in prior_vent_deps}
            pay_map = {x["venture_account__venture_type__name"]: Decimal(str(x["total"])) for x in prior_vent_pays}
            for name in all_venture_types.keys():
                prior_balances["venture_net"][name] = dep_map.get(name, Decimal("0")) - pay_map.get(name, Decimal("0"))

            # --- LOANS ---
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
            "guarantees": defaultdict(Decimal),
        }

        # === FETCH GUARANTOR PROFILE ===
        try:
            guarantor_profile = GuarantorProfile.objects.get(member=member)
            total_active_guarantees = guarantor_profile.committed_guarantee_amount
        except GuarantorProfile.DoesNotExist:
            total_active_guarantees = Decimal("0")

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

            savings_by_type = defaultdict(lambda: {"total": Decimal("0"), "deposits": []})
            for dep in savings_deps:
                stype = dep.savings_account.account_type.name
                amount = Decimal(str(dep.amount))
                savings_by_type[stype]["total"] += amount
                savings_by_type[stype]["deposits"].append({"type": stype, "amount": float(amount)})
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
                vent_by_type[vtype]["deposits"].append({"venture_type": vtype, "amount": float(amount)})
                yearly["vent_dep"][vtype] += amount

            for pay in vent_pays:
                vtype = pay.venture_account.venture_type.name
                amount = Decimal(str(pay.amount))
                vent_by_type[vtype]["payments"].append({"venture_type": vtype, "amount": float(amount)})
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

            loan_by_type = defaultdict(lambda: {"disbursed": [], "repaid": [], "interest": []})
            for d in disbursements:
                ltype = d.loan_account.loan_type.name
                amount = Decimal(str(d.amount))
                loan_by_type[ltype]["disbursed"].append({"loan_type": ltype, "amount": float(amount)})
                yearly["loan_disb"][ltype] += amount

            for r in repayments:
                ltype = r.loan_account.loan_type.name
                amount = Decimal(str(r.amount))
                if r.repayment_type != "Interest Payment":
                    loan_by_type[ltype]["repaid"].append({"loan_type": ltype, "amount": float(amount)})
                    yearly["loan_rep"][ltype] += amount

            for i in interests:
                ltype = i.loan_account.loan_type.name
                amount = Decimal(str(i.amount))
                loan_by_type[ltype]["interest"].append({"loan_type": ltype, "amount": float(amount)})
                yearly["loan_int"][ltype] += amount

            # === GUARANTEES (NEW) ===
            new_guarantees = GuaranteeRequest.objects.filter(
                guarantor__member=member,
                status="Accepted",
                created_at__year=year,
                created_at__month=month,
            ).select_related("member") # The person being guaranteed

            guarantee_data = {"total_new": Decimal("0"), "transactions": []}
            for gr in new_guarantees:
                amount = gr.guaranteed_amount
                current = gr.current_balance if gr.current_balance is not None else amount
                guarantee_data["total_new"] += amount
                yearly["guarantees"]["new"] += amount
                guarantee_data["transactions"].append({
                    "borrower_name": f"{gr.member.first_name} {gr.member.last_name}",
                    "borrower_no": gr.member.member_no,
                    "amount": float(amount),
                    "current_balance": float(current),
                    "date": gr.created_at.strftime("%Y-%m-%d"),
                })

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

            # === CALCULATE MONTHLY TOTALS ===
            total_savings_month = sum(item["total"] for item in savings_by_type.values())
            total_vent_dep_month = sum(sum(d["amount"] for d in data["deposits"]) for data in vent_by_type.values())
            total_vent_pay_month = sum(sum(p["amount"] for p in data["payments"]) for data in vent_by_type.values())
            total_vent_balance_month = total_vent_dep_month - total_vent_pay_month

            total_loan_disb_month = sum(sum(d["amount"] for d in data["disbursed"]) for data in loan_by_type.values())
            total_loan_rep_month = sum(sum(r["amount"] for r in data["repaid"]) for data in loan_by_type.values())
            total_loan_int_month = sum(sum(i["amount"] for i in data["interest"]) for data in loan_by_type.values())
            total_loan_out_month = sum(running["loan_out"].values())

            # === ENHANCE by_type WITH TOTALS ===
            enhanced_savings = []
            for name in all_savings_types.keys():
                data = savings_by_type.get(name, {"total": Decimal("0"), "deposits": []})
                monthly_total = data["total"]
                brought = running["savings"][name] - monthly_total
                enhanced_savings.append({
                    "type": name,
                    "amount": float(monthly_total),
                    "total_deposits": float(monthly_total),
                    "deposits": data["deposits"],
                    "balance_brought_forward": float(brought),
                    "balance_carried_forward": float(running["savings"][name]),
                })

            enhanced_ventures = []
            for name in all_venture_types.keys():
                data = vent_by_type.get(name, {"deposits": [], "payments": []})
                dep_total = sum(d["amount"] for d in data["deposits"])
                pay_total = sum(p["amount"] for p in data["payments"])
                net_month = dep_total - pay_total
                brought = running["venture_net"][name] - Decimal(str(net_month))
                enhanced_ventures.append({
                    "venture_type": name,
                    "total_venture_deposits": float(dep_total),
                    "total_venture_payments": float(pay_total),
                    "venture_deposits_transactions": data["deposits"],
                    "venture_payments_transactions": data["payments"],
                    "balance_brought_forward": float(brought),
                    "balance_carried_forward": float(running["venture_net"][name]),
                })

            enhanced_loans = []
            for name in all_loan_types.keys():
                data = loan_by_type.get(name, {"disbursed": [], "repaid": [], "interest": []})
                disb_total = sum(d["amount"] for d in data["disbursed"])
                rep_total = sum(r["amount"] for r in data["repaid"])
                int_total = sum(i["amount"] for i in data["interest"])
                net_month = disb_total - rep_total
                brought = running["loan_out"][name] - Decimal(str(net_month))
                enhanced_loans.append({
                    "loan_type": name,
                    "total_amount_disbursed": float(disb_total),
                    "total_amount_repaid": float(rep_total),
                    "total_interest_charged": float(int_total),
                    "total_amount_outstanding": float(running["loan_out"][name]),
                    "total_amount_disbursed_transactions": data["disbursed"],
                    "total_amount_repaid_transactions": data["repaid"],
                    "total_interest_charged_transactions": data["interest"],
                    "balance_brought_forward": float(brought),
                    "balance_carried_forward": float(running["loan_out"][name]),
                })

            # === APPEND MONTH WITH FULL SUMMARY + TOTAL BALANCE ===
            monthly_summary.append({
                "month": month_key,
                "savings": {
                    "total_savings": float(total_savings_month),
                    "total_savings_deposits": float(total_savings_month),
                    "total_balance": float(sum(running["savings"].values())),
                    "by_type": enhanced_savings,
                },
                "ventures": {
                    "venture_deposits": float(total_vent_dep_month),
                    "venture_payments": float(total_vent_pay_month),
                    "venture_balance": float(total_vent_balance_month),
                    "total_balance": float(sum(running["venture_net"].values())),
                    "by_type": enhanced_ventures,
                },
                "loans": {
                    "total_loans_disbursed": float(total_loan_disb_month),
                    "total_loans_repaid": float(total_loan_rep_month),
                    "total_interest_charged": float(total_loan_int_month),
                    "total_loans_outstanding": float(total_loan_out_month),
                    "total_balance": float(sum(running["loan_out"].values())),
                    "by_type": enhanced_loans,
                },
                "guarantees": {
                    "new_guarantees": float(guarantee_data["total_new"]),
                    "transactions": guarantee_data["transactions"],
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
                    "total_guaranteed_active": float(total_active_guarantees),
                    "total_new_guarantees": float(total_new_guarantees),
                    "year_end_balances": year_end_balances,
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
            display_header_footer=False,
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

        # === PREPARE TABLE DATA ===
        # 1. Extract unique types (sorted)
        savings_types = set()
        venture_types = set()
        loan_types = set()

        for m in data["monthly_summary"]:
            for s in m["savings"]["by_type"]:
                savings_types.add(s["type"])
            for v in m["ventures"]["by_type"]:
                venture_types.add(v["venture_type"])
            for l in m["loans"]["by_type"]:
                loan_types.add(l["loan_type"])

        savings_types = sorted(list(savings_types))
        venture_types = sorted(list(venture_types))
        loan_types = sorted(list(loan_types))

        # Total Active Guarantees
        total_active_guarantees = data["summary"].get("total_guaranteed_active", 0)

        # 2. Build rows
        table_rows = []
        for m in data["monthly_summary"]:
            row = {
                "month": m["month"],
                "savings": [],
                "ventures": [],
                "loans": [],
                "guarantees": m.get("guarantees", {}).get("new_guarantees", 0)
            }

            # Savings
            s_map = {item["type"]: item for item in m["savings"]["by_type"]}
            for t in savings_types:
                item = s_map.get(t)
                row["savings"].append({
                    "type": t,
                    "dep": item["amount"] if item else 0,
                    "bal": item["balance_carried_forward"] if item else 0,
                    "exists": bool(item)
                })

            # Ventures
            v_map = {item["venture_type"]: item for item in m["ventures"]["by_type"]}
            for t in venture_types:
                item = v_map.get(t)
                row["ventures"].append({
                    "type": t,
                    "dep": item["total_venture_deposits"] if item else 0,
                    "pay": item["total_venture_payments"] if item else 0,
                    "bal": item["balance_carried_forward"] if item else 0,
                    "exists": bool(item)
                })

            # Loans
            l_map = {item["loan_type"]: item for item in m["loans"]["by_type"]}
            for t in loan_types:
                item = l_map.get(t)
                row["loans"].append({
                    "type": t,
                    "disb": item["total_amount_disbursed"] if item else 0,
                    "rep": item["total_amount_repaid"] if item else 0,
                    "int": item["total_interest_charged"] if item else 0,
                    "out": item["total_amount_outstanding"] if item else 0,
                    "exists": bool(item)
                })

            table_rows.append(row)

        # Render HTML with logo
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
                "table_rows": table_rows,
                "total_active_guarantees": total_active_guarantees,
                "chart_of_accounts": data["chart_of_accounts"]
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
