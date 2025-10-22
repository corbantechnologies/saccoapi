from rest_framework import generics
from rest_framework.permissions import IsAuthenticated
from django.contrib.auth import get_user_model
from django.http import StreamingHttpResponse
from savings.models import SavingsType
from ventures.models import VentureType
from transactions.serializers import AccountSerializer
import csv
import io
from datetime import datetime
import cloudinary.uploader

from transactions.models import DownloadLog

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


class AccountListDownloadView(generics.ListAPIView):
    serializer_class = AccountSerializer
    permission_classes = (IsAuthenticated,)

    def get_queryset(self):
        return (
            User.objects.all()
            .filter(is_member=True)
            .prefetch_related("savings_accounts", "venture_accounts")
        )

    def get(self, request, *args, **kwargs):
        # get all savings and venture types
        savings_types = SavingsType.objects.all().values_list("name", flat=True)
        venture_types = VentureType.objects.all().values_list("name", flat=True)

        # Define CSV headers
        headers = ["Member Number", "Member Name"]
        for stype in savings_types:
            headers.extend([f"{stype} Account", f"{stype} Balance"])
        for vtype in venture_types:
            headers.extend([f"{vtype} Account", f"{vtype} Balance"])

        # CSV Buffer
        buffer = io.StringIO()
        writer = csv.DictWriter(buffer, fieldnames=headers, lineterminator="\n")
        writer.writeheader()

        # serialize data
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)
        data = serializer.data

        # write rows
        for user in data:
            row = {
                "Member Number": user["member_no"],
                "Member Name": user["member_name"],
            }
            # Initialize all account/balance fields as empty
            for stype in savings_types:
                row[f"{stype} Account"] = ""
                row[f"{stype} Balance"] = ""
            for vtype in venture_types:
                row[f"{vtype} Account"] = ""
                row[f"{vtype} Balance"] = ""

            # Populate savings accounts
            for acc_no, acc_type, balance in user["savings_accounts"]:
                row[f"{acc_type} Account"] = acc_no
                row[f"{acc_type} Balance"] = f"{balance:.2f}"

            # Populate venture accounts
            for acc_no, acc_type, balance in user["venture_accounts"]:
                row[f"{acc_type} Account"] = acc_no
                row[f"{acc_type} Balance"] = f"{balance:.2f}"

            writer.writerow(row)

        # upload to cloudinary
        buffer.seek(0)
        file_name = f"account_list_{datetime.now().strftime('%Y%m%d')}.csv"
        upload_result = cloudinary.uploader.upload(
            buffer,
            resource_type="raw",
            public_id=f"account_lists/{file_name}",
            format="csv",
        )

        # log the download
        DownloadLog.objects.create(
            admin=request.user,
            file_name=file_name,
            cloudinary_url=upload_result["secure_url"],
        )

        # Prepare response
        buffer.seek(0)
        response = StreamingHttpResponse(buffer, content_type="text/csv")
        response["Content-Disposition"] = f"attachment; filename={file_name}"

        return response
