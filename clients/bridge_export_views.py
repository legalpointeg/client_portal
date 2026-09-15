"""
client_portal/clients/bridge_export_views.py
-------------------------------------------------------------
Endpoints محمية بـ API key بترجّع بيانات جديدة من client_portal
عشان lawfirm_portal يسحبها (مزامنة عكسية). نفس فكرة وأسلوب
bridge/portal_export_views.py الموجود في lawfirm_portal، بس بالاتجاه المعاكس.
"""
import json

from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from clients.models import Consultation


def _check_api_key(request):
    """يتحقق من header X-API-Key. يرجع True لو صح."""
    provided = request.headers.get('X-API-Key', '')
    expected = getattr(settings, 'PORTAL_SYNC_API_KEY', None)
    return bool(expected) and provided == expected


@csrf_exempt
@require_GET
def pending_consultations(request):
    """يرجّع الاستشارات اللي لسه ما اتزامنتش مع lawfirm_portal."""
    if not _check_api_key(request):
        return JsonResponse({'ok': False, 'message': 'Unauthorized'}, status=401)

    qs = Consultation.objects.filter(synced_to_lawfirm=False).values(
        'id', 'client_id', 'subject', 'question_text', 'status',
        'is_urgent', 'created_at',
    )
    data = []
    for c in qs:
        data.append({
            'id': str(c['id']),
            'client_id': str(c['client_id']),
            'subject': c['subject'],
            'question_text': c['question_text'],
            'status': c['status'],
            'is_urgent': c['is_urgent'],
            'created_at': c['created_at'].isoformat(),
        })
    return JsonResponse({'ok': True, 'count': len(data), 'consultations': data})


@csrf_exempt
@require_POST
def mark_consultations_synced(request):
    """يعلّم على استشارات معينة إنها اتزامنت بنجاح (يستلم قائمة IDs)."""
    if not _check_api_key(request):
        return JsonResponse({'ok': False, 'message': 'Unauthorized'}, status=401)

    try:
        data = json.loads(request.body)
        ids = data.get('ids', [])
    except (json.JSONDecodeError, AttributeError):
        return JsonResponse({'ok': False, 'message': 'بيانات غير صحيحة'}, status=400)

    updated = Consultation.objects.filter(id__in=ids).update(synced_to_lawfirm=True)
    return JsonResponse({'ok': True, 'updated': updated})
