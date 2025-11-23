import os
import django
from decimal import Decimal

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "saccoapi.settings")
django.setup()

from django.contrib.auth import get_user_model
from loanapplications.models import LoanApplication
from loantypes.models import LoanType
from guarantorprofile.models import GuarantorProfile
from guaranteerequests.models import GuaranteeRequest
from loanapplications.utils import compute_loan_coverage
from django.test import RequestFactory
from loanapplications.views import (
    SubmitLoanApplicationView, 
    SubmitForAmendmentView, 
    AdminAmendView, 
    MemberAcceptAmendmentView
)
from guaranteerequests.views import GuaranteeRequestUpdateStatusView

User = get_user_model()

def run_verification():
    print("--- Starting Verification ---")
    
    # 1. Setup Users
    member, _ = User.objects.get_or_create(username="member_test", email="member@test.com", member_no="M001")
    guarantor_user, _ = User.objects.get_or_create(username="guarantor_test", email="guarantor@test.com", member_no="G001")
    
    # Ensure profiles
    GuarantorProfile.objects.get_or_create(member=member, defaults={"max_guarantee_amount": 100000})
    g_profile, _ = GuarantorProfile.objects.get_or_create(member=guarantor_user, defaults={"max_guarantee_amount": 100000})
    
    # Reset commitment
    g_profile.committed_guarantee_amount = 0
    g_profile.save()
    
    # 2. Create Loan Type
    product, _ = LoanType.objects.get_or_create(name="TestLoan", defaults={"interest_rate": 10})
    
    # 3. Create Application
    print("\n1. Creating Loan Application...")
    app = LoanApplication.objects.create(
        member=member,
        product=product,
        requested_amount=50000,
        calculation_mode="fixed_term",
        term_months=12,
        start_date="2023-01-01"
    )
    print(f"Status: {app.status} (Expected: Pending)")
    assert app.status == "Pending"
    
    # 4. Submit for Amendment
    print("\n2. Submitting for Amendment...")
    factory = RequestFactory()
    request = factory.post(f"/loanapplications/{app.reference}/submit-amendment/")
    request.user = member
    view = SubmitForAmendmentView.as_view()
    view(request, reference=app.reference)
    
    app.refresh_from_db()
    print(f"Status: {app.status} (Expected: Ready for Amendment)")
    assert app.status == "Ready for Amendment"
    
    # 5. Admin Amends
    print("\n3. Admin Amends...")
    request = factory.patch(f"/loanapplications/{app.reference}/amend/", {"requested_amount": 60000}, content_type="application/json")
    request.user = member # Mocking admin rights check bypass for simplicity or assume admin
    # Note: View checks IsSystemAdminOrReadOnly, so we might need a superuser. 
    # For this script, let's just manually update status to simulate admin action if permission fails, 
    # but let's try to do it right.
    admin, _ = User.objects.get_or_create(username="admin_test", is_staff=True, is_superuser=True)
    request.user = admin
    view = AdminAmendView.as_view()
    view(request, reference=app.reference)
    
    app.refresh_from_db()
    print(f"Status: {app.status} (Expected: Amended)")
    print(f"Amount: {app.requested_amount} (Expected: 60000)")
    assert app.status == "Amended"
    assert app.requested_amount == 60000
    
    # 6. Member Accepts
    print("\n4. Member Accepts...")
    request = factory.post(f"/loanapplications/{app.reference}/accept-amendment/")
    request.user = member
    view = MemberAcceptAmendmentView.as_view()
    view(request, reference=app.reference)
    
    app.refresh_from_db()
    print(f"Status: {app.status} (Expected: In Progress - since not covered)")
    assert app.status == "In Progress"
    
    # 7. Request Guarantee
    print("\n5. Requesting Guarantee...")
    gr = GuaranteeRequest.objects.create(
        member=member,
        loan_application=app,
        guarantor=g_profile,
        guaranteed_amount=60000
    )
    
    # 8. Guarantor Accepts (with edit?)
    print("\n6. Guarantor Accepts...")
    # Let's say they accept 60000
    request = factory.patch(f"/guaranteerequests/{gr.reference}/status/", {"status": "Accepted"}, content_type="application/json")
    request.user = guarantor_user
    view = GuaranteeRequestUpdateStatusView.as_view()
    view(request, reference=gr.reference)
    
    gr.refresh_from_db()
    g_profile.refresh_from_db()
    print(f"GR Status: {gr.status} (Expected: Accepted)")
    print(f"Guarantor Committed: {g_profile.committed_guarantee_amount} (Expected: 0 - Deferred)")
    assert gr.status == "Accepted"
    assert g_profile.committed_guarantee_amount == 0
    
    app.refresh_from_db()
    print(f"App Status: {app.status} (Expected: Ready for Submission)")
    assert app.status == "Ready for Submission"
    
    # 9. Submit Application
    print("\n7. Submitting Application...")
    request = factory.post(f"/loanapplications/{app.reference}/submit/")
    request.user = member
    view = SubmitLoanApplicationView.as_view()
    view(request, reference=app.reference)
    
    app.refresh_from_db()
    g_profile.refresh_from_db()
    print(f"App Status: {app.status} (Expected: Submitted)")
    print(f"Guarantor Committed: {g_profile.committed_guarantee_amount} (Expected: 60000)")
    assert app.status == "Submitted"
    assert g_profile.committed_guarantee_amount == 60000
    
    print("\n--- Verification Successful ---")

if __name__ == "__main__":
    run_verification()
