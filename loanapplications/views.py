# loanapplications/views.py
from rest_framework import generics, status, serializers
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.db import transaction
from django.db.models import F

from .models import LoanApplication
from .serializers import LoanApplicationSerializer, LoanStatusUpdateSerializer
from accounts.permissions import IsSystemAdminOrReadOnly
from guaranteerequests.models import GuaranteeRequest
from guarantorprofile.models import GuarantorProfile
from loans.models import LoanAccount
from .utils import compute_loan_coverage


# ——————————————————————————————————————————————————————————————
# 1. List / Create / Detail
# ——————————————————————————————————————————————————————————————
class LoanApplicationListCreateView(generics.ListCreateAPIView):
    queryset = LoanApplication.objects.all()
    serializer_class = LoanApplicationSerializer
    permission_classes = [IsAuthenticated]

    def perform_create(self, serializer):
        serializer.save(member=self.request.user)

    def get_queryset(self):
        return self.queryset.filter(member=self.request.user)


class LoanApplicationDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = LoanApplication.objects.all()
    serializer_class = LoanApplicationSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = "reference"

    def patch(self, request, *args, **kwargs):
        return self.partial_update(request, *args, **kwargs)


class LoanApplicationListView(generics.ListAPIView):
    queryset = LoanApplication.objects.all()
    serializer_class = LoanApplicationSerializer
    permission_classes = [IsSystemAdminOrReadOnly]


# ——————————————————————————————————————————————————————————————
# 2. Submit Application (Member) — Link to Existing LoanAccount
# ——————————————————————————————————————————————————————————————
class SubmitLoanApplicationView(generics.GenericAPIView):
    queryset = LoanApplication.objects.all()
    serializer_class = LoanApplicationSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = "reference"

    def post(self, request, reference):
        app = self.get_object()

        # 1. Ownership
        if app.member != request.user:
            return Response(
                {"detail": "You can only submit your own applications."},
                status=status.HTTP_403_FORBIDDEN,
            )

        # 2. Must be ready
        if app.status not in ["Ready for Submission", "Submitted"]:
            return Response(
                {"detail": "Application is not ready for submission."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if app.status == "Submitted":
            return Response(
                {"detail": "Already submitted."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # 3. Full coverage
        coverage = compute_loan_coverage(app)
        if not coverage["is_fully_covered"]:
            return Response(
                {"detail": "Guarantees do not cover full amount."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        with transaction.atomic():
            app.status = "Submitted"
            app.save(update_fields=["status"])

            # 2. Auto self-guarantee
            if (
                coverage["is_fully_covered"]
                and coverage["total_guaranteed_by_others"] == 0
            ):
                try:
                    profile = GuarantorProfile.objects.select_for_update().get(
                        member=app.member
                    )
                    required = app.requested_amount

                    if (
                        profile.committed_guarantee_amount + required
                        > profile.max_guarantee_amount
                    ):
                        raise ValueError("Insufficient capacity")

                    # Update profile
                    profile.committed_guarantee_amount += required
                    profile.save(update_fields=["committed_guarantee_amount"])

                    # Create GuaranteeRequest
                    GuaranteeRequest.objects.create(
                        member=app.member,
                        loan_application=app,
                        guarantor=profile,
                        guaranteed_amount=required,
                        status="Accepted",
                    )

                    # Update application
                    app.self_guaranteed_amount = required
                    app.save(update_fields=["self_guaranteed_amount"])

                except (GuarantorProfile.DoesNotExist, ValueError):
                    app.status = "Ready for Submission"
                    app.save(update_fields=["status"])
                    return Response(
                        {"detail": "Self-guarantee failed."},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

        return Response(
            {
                "detail": "Loan application submitted successfully.",
                "application": LoanApplicationSerializer(
                    app, context=self.get_serializer_context()
                ).data,
            },
            status=status.HTTP_200_OK,
        )


# ——————————————————————————————————————————————————————————————
# 3. Approve / Decline (Admin Only)
# ——————————————————————————————————————————————————————————————
class ApproveOrDeclineLoanApplicationView(generics.RetrieveUpdateAPIView):
    queryset = LoanApplication.objects.all()
    permission_classes = [IsAuthenticated, IsSystemAdminOrReadOnly]
    lookup_field = "reference"

    def get_serializer_class(self):
        return (
            LoanApplicationSerializer
            if self.request.method == "GET"
            else LoanStatusUpdateSerializer
        )

    @transaction.atomic
    def perform_update(self, serializer):
        app = serializer.instance
        new_status = serializer.validated_data["status"]

        if app.status != "Submitted":
            raise serializers.ValidationError(
                {"status": f"Cannot {new_status.lower()} in '{app.status}' state."}
            )

        if new_status == "Approved":
            # LINK ON APPROVAL
            try:
                loan_account = LoanAccount.objects.get(
                    member=app.member, loan_type=app.product, is_active=True
                )
            except LoanAccount.DoesNotExist:
                raise serializers.ValidationError(
                    {
                        "status": "No active loan account found for this member and loan type."
                    }
                )

            app.loan_account = loan_account
            app.status = "Approved"
            app.save(update_fields=["loan_account", "status"])

        elif new_status == "Declined":
            with transaction.atomic():
                # === 1. REVERT SELF-GUARANTEE ===
                if app.self_guaranteed_amount > 0:
                    try:
                        profile = app.member.guarantor_profile
                        current = profile.committed_guarantee_amount
                        to_revert = app.self_guaranteed_amount

                        if current < to_revert:
                            # Safety: Don't go negative
                            to_revert = current

                        profile.committed_guarantee_amount = (
                            F("committed_guarantee_amount") - to_revert
                        )
                        profile.max_active_guarantees -= 1
                        profile.save(
                            update_fields=[
                                "committed_guarantee_amount",
                                "max_active_guarantees",
                            ]
                        )
                        profile.refresh_from_db()  # Critical!

                        # Reset app
                        app.self_guaranteed_amount = 0
                        app.save(update_fields=["self_guaranteed_amount"])

                    except GuarantorProfile.DoesNotExist:
                        pass

                # === 2. REVERT EXTERNAL GUARANTORS ===
                for gr in app.guarantors.filter(status="Accepted"):
                    profile = gr.guarantor
                    current = profile.committed_guarantee_amount
                    to_revert = gr.guaranteed_amount

                    if current < to_revert:
                        to_revert = current

                    profile.committed_guarantee_amount = (
                        F("committed_guarantee_amount") - to_revert
                    )
                    profile.save(update_fields=["committed_guarantee_amount"])
                    profile.refresh_from_db()

                    gr.status = "Cancelled"
                    gr.save(update_fields=["status"])

                # === 3. UPDATE STATUS ===
                app.status = "Declined"
                app.save(update_fields=["status"])

            # Only save once
            serializer.save(status="Declined")

    def update(self, request, *args, **kwargs):
        response = super().update(request, *args, **kwargs)
        app = self.get_object()
        data = {
            "detail": f"Application {app.status.lower()}.",
            "application": LoanApplicationSerializer(
                app, context=self.get_serializer_context()
            ).data,
        }

        return Response(data, status=status.HTTP_200_OK)


# ——————————————————————————————————————————————————————————————
# 4. Disburse (Admin Only) — Add to LoanAccount balance
# ——————————————————————————————————————————————————————————————
class DisburseLoanApplicationView(generics.GenericAPIView):
    queryset = LoanApplication.objects.all()
    permission_classes = [IsAuthenticated, IsSystemAdminOrReadOnly]
    lookup_field = "reference"

    def post(self, request, reference):
        app = self.get_object()

        if app.status != "Approved":
            return Response(
                {"detail": "Application must be approved first."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not app.loan_account:
            return Response(
                {"detail": "No linked loan account."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        with transaction.atomic():
            app.loan_account.outstanding_balance += app.requested_amount
            app.loan_account.save(update_fields=["outstanding_balance"])

            app.status = "Disbursed"
            app.save(update_fields=["status"])

        return Response(
            {
                "detail": "Loan disbursed successfully.",
                "disbursed_amount": float(app.requested_amount),
                "new_balance": float(app.loan_account.outstanding_balance),
                "account_number": app.loan_account.account_number,
            },
            status=status.HTTP_200_OK,
        )
