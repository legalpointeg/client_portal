import json
import os

from django.http import JsonResponse
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from .models import ClientUpload

SHARED_SECRET = os.environ.get("UPLOAD_WEBHOOK_SECRET", "غيّر_هذا_المفتاح")


@csrf_exempt
@require_POST
def receive_upload(request):
    if request.headers.get("X-Webhook-Secret") != SHARED_SECRET:
        return JsonResponse({"error": "unauthorized"}, status=401)

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "invalid payload"}, status=400)

    client_id = data.get("client_id")
    file_name = data.get("file_name")
    drive_url = data.get("drive_url")
    uploaded_at = parse_datetime(data.get("uploaded_at") or "") or timezone.now()

    if not all([client_id, file_name, drive_url]):
        return JsonResponse(
            {"error": "missing fields: client_id, file_name, drive_url required"},
            status=400,
        )

    ClientUpload.objects.create(
        client_id=client_id,
        file_name=file_name,
        drive_url=drive_url,
        uploaded_at=uploaded_at,
    )
    return JsonResponse({"status": "received"}, status=200)


def list_client_uploads(request, client_id):
    uploads = ClientUpload.objects.filter(client_id=client_id).order_by("-uploaded_at")
    data = [
        {
            "file_name": u.file_name,
            "drive_url": u.drive_url,
            "uploaded_at": u.uploaded_at.isoformat(),
        }
        for u in uploads
    ]
    return JsonResponse(data, safe=False)


def health_check(request):
    return JsonResponse({"status": "ok", "service": "legalbridgeeg upload receiver"})
