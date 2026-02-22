from django.urls import path


from memberfees.views import MemberFeeListView, MemberFeeRetrieveView


urlpatterns = [
    path("", MemberFeeListView.as_view(), name="memberfee-list"),
    path("<str:reference>/", MemberFeeRetrieveView.as_view(), name="memberfee-retrieve"),
]