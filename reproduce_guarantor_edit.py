
import os
import django
from decimal import Decimal
from rest_framework.test import APIClient
from django.contrib.auth import get_user_model

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "saccoapi.settings")
django.setup()

from loanapplications.models import LoanApplication
from loantypes.models import LoanType
from guarantorprofile.models import GuarantorProfile
from guaranteerequests.models import GuaranteeRequest
from loans.models import LoanAccount

User = get_user_model()

def run():
    # Cleanup
    User.objects.filter(username__in=["member1", "guarantor1"]).delete()
    LoanType.objects.filter(name="Test Loan").delete()

    # Create users
    member = User.objects.create_user(username="member1", password="password", member_no="MEM001")
    guarantor_user = User.objects.create_user(username="guarantor1", password="password", member_no="GUA001")

    # Create Guarantor Profile
    guarantor_profile = GuarantorProfile.objects.create(
        member=guarantor_user,
        is_eligible=True,
        max_guarantee_amount=Decimal("100000.00")
    )

    # Create Loan Type
    loan_type = LoanType.objects.create(
        name="Test Loan",
        interest_rate=Decimal("10.00"),
        max_amount=Decimal("50000.00"),
        min_amount=Decimal("1000.00"),
        max_repayment_period=12
    )

    # Create Loan Application
    loan_app = LoanApplication.objects.create(
        member=member,
        product=loan_type,
        requested_amount=Decimal("50000.00"),
        repayment_frequency="monthly",
        start_date="2023-01-01",
        term_months=12,
        status="Ready for Submission" # Needs to be in a state that allows guarantee requests? 
                                      # Actually GuaranteeRequestSerializer checks if loan_app.status is NOT in FINAL_STATES
                                      # "Ready for Submission" is fine.
    )

    # Create Guarantee Request
    request = GuaranteeRequest.objects.create(
        member=member,
        loan_application=loan_app,
        guarantor=guarantor_profile,
        guaranteed_amount=Decimal("50000.00"),
        status="Pending"
    )

    print(f"Initial Guaranteed Amount: {request.guaranteed_amount}")

    # Test Update
    client = APIClient()
    client.force_authenticate(user=guarantor_user)

    url = f"/api/guaranteerequests/{request.reference}/status/"
    data = {
        "status": "Accepted",
        "guaranteed_amount": "40000.00"
    }

    response = client.patch(url, data, format='json')

    print(f"Response Status: {response.status_code}")
    print(f"Response Data: {response.data}")

    request.refresh_from_db()
    print(f"Updated Guaranteed Amount: {request.guaranteed_amount}")

    if request.guaranteed_amount == Decimal("40000.00"):
        print("SUCCESS: Guarantor amount updated successfully.")
    else:
        print("FAILURE: Guarantor amount NOT updated.")

if __name__ == "__main__":
    run()
