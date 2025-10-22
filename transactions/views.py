from rest_framework import generics
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.contrib.auth import get_user_model

from transactions.serializers import AccountSerializer

User = get_user_model()


class AccountListView(generics.ListAPIView):
    serializer_class = AccountSerializer
    permission_classes = (AllowAny,)

    def get_queryset(self):
        return User.objects.all().prefetch_related(
            "savings_accounts", "loans", "venture_accounts"
        )
