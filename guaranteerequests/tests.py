
from decimal import Decimal
from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase
from rest_framework import status

from loanapplications.models import LoanApplication
from loantypes.models import LoanType
from guarantorprofile.models import GuarantorProfile
from guaranteerequests.models import GuaranteeRequest

User = get_user_model()

class GuarantorAmountEditTests(APITestCase):
    def setUp(self):
        # Create users
        self.member = User.objects.create_user(username="member", password="password", member_no="MEM001")
        self.guarantor_user = User.objects.create_user(username="guarantor", password="password", member_no="GUA001")

        # Create Guarantor Profile
        self.guarantor_profile = GuarantorProfile.objects.create(
            member=self.guarantor_user,
            is_eligible=True,
            max_guarantee_amount=Decimal("100000.00")
        )

        # Create Loan Type
        self.loan_type = LoanType.objects.create(
            name="Test Loan",
            interest_rate=Decimal("10.00"),
            max_amount=Decimal("50000.00"),
            min_amount=Decimal("1000.00"),
            max_repayment_period=12
        )

        # Create Loan Application
        self.loan_app = LoanApplication.objects.create(
            member=self.member,
            product=self.loan_type,
            requested_amount=Decimal("50000.00"),
            repayment_frequency="monthly",
            start_date="2023-01-01",
            term_months=12,
            status="Ready for Submission"
        )

        # Create Guarantee Request
        self.request = GuaranteeRequest.objects.create(
            member=self.member,
            loan_application=self.loan_app,
            guarantor=self.guarantor_profile,
            guaranteed_amount=Decimal("50000.00"),
            status="Pending"
        )

        self.url = f"/api/guaranteerequests/{self.request.reference}/status/"

    def test_guarantor_can_edit_amount_within_limit(self):
        self.client.force_authenticate(user=self.guarantor_user)
        data = {
            "status": "Accepted",
            "guaranteed_amount": "40000.00"
        }
        response = self.client.patch(self.url, data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.request.refresh_from_db()
        self.assertEqual(self.request.guaranteed_amount, Decimal("40000.00"))
        self.assertEqual(self.request.status, "Accepted")

    def test_guarantor_cannot_exceed_limit(self):
        self.client.force_authenticate(user=self.guarantor_user)
        # Limit is 100,000. Try to set to 150,000
        data = {
            "status": "Accepted",
            "guaranteed_amount": "150000.00"
        }
        response = self.client.patch(self.url, data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("guaranteed_amount", response.data)
        self.request.refresh_from_db()
        self.assertEqual(self.request.status, "Pending") # Should not change

    def test_guarantor_cannot_set_negative_amount(self):
        self.client.force_authenticate(user=self.guarantor_user)
        data = {
            "status": "Accepted",
            "guaranteed_amount": "-100.00"
        }
        response = self.client.patch(self.url, data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("guaranteed_amount", response.data)

    def test_guarantor_cannot_edit_when_declining(self):
        self.client.force_authenticate(user=self.guarantor_user)
        # Even if they send an amount, it should be ignored or at least not validated?
        # Actually, if they decline, we don't care about the amount.
        # But let's see if the serializer allows it.
        # The view logic:
        # if new_status == "Accepted": update amount
        # So if Declined, amount is ignored.
        data = {
            "status": "Declined",
            "guaranteed_amount": "150000.00" # Invalid amount
        }
        response = self.client.patch(self.url, data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.request.refresh_from_db()
        self.assertEqual(self.request.status, "Declined")
        self.assertEqual(self.request.guaranteed_amount, Decimal("50000.00")) # Should remain original

    def test_guarantor_can_edit_amount_after_acceptance(self):
        # First accept
        self.client.force_authenticate(user=self.guarantor_user)
        data = {
            "status": "Accepted",
            "guaranteed_amount": "50000.00"
        }
        response = self.client.patch(self.url, data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Now edit amount
        data = {
            "status": "Accepted",
            "guaranteed_amount": "30000.00"
        }
        response = self.client.patch(self.url, data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.request.refresh_from_db()
        self.assertEqual(self.request.guaranteed_amount, Decimal("30000.00"))

