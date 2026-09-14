"""
client_portal/clients/management/commands/sync_task_taxonomy.py
-------------------------------------------------------------
management command بيسحب جداول التصنيف الميداني الخمسة من lawfirm_portal
(endpoint bridge/portal-export/task-taxonomy/) بالترتيب الصحيح للاعتماديات.
"""
import json
import urllib.error
import urllib.request

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from clients.models import CaseSection, CourtSector, CourtAuthority, CourtDivision, CourtEntity


class Command(BaseCommand):
    help = 'يسحب جداول التصنيف الميداني الخمسة من lawfirm_portal.'

    def handle(self, *args, **options):
        base_url = getattr(settings, 'LAWFIRM_API_BASE_URL', '').rstrip('/')
        api_key = getattr(settings, 'PORTAL_SYNC_API_KEY', '')

        if not base_url or not api_key:
            raise CommandError('لازم تضبط LAWFIRM_API_BASE_URL و PORTAL_SYNC_API_KEY في settings.py أولاً.')

        url = f'{base_url}/bridge/portal-export/task-taxonomy/'
        request = urllib.request.Request(url, headers={'X-API-Key': api_key})

        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                payload = json.loads(response.read().decode('utf-8'))
        except urllib.error.HTTPError as e:
            raise CommandError(f'فشل الاتصال بـ lawfirm_portal - HTTP {e.code}: {e.reason}')
        except urllib.error.URLError as e:
            raise CommandError(f'تعذر الوصول لـ lawfirm_portal: {e.reason}')

        if not payload.get('ok'):
            raise CommandError(f'lawfirm_portal رجّع خطأ: {payload.get("message")}')

        counts = {}

        for item in payload.get('sections', []):
            CaseSection.objects.update_or_create(
                id=item['id'],
                defaults={'code': item['code'], 'name': item['name'], 'order': item['order']},
            )
        counts['sections'] = len(payload.get('sections', []))

        for item in payload.get('sectors', []):
            CourtSector.objects.update_or_create(
                id=item['id'],
                defaults={'code': item['code'], 'name': item['name'], 'order': item['order'], 'notes': item['notes'] or ''},
            )
        counts['sectors'] = len(payload.get('sectors', []))

        for item in payload.get('authorities', []):
            CourtAuthority.objects.update_or_create(
                id=item['id'],
                defaults={
                    'sector_id': item['sector_id'], 'name': item['name'],
                    'authority_type': item['authority_type'] or '', 'address': item['address'] or '',
                    'phone': item['phone'] or '', 'working_hours': item['working_hours'] or '',
                    'access_method': item['access_method'] or '', 'access_duration': item['access_duration'] or '',
                    'notes': item['notes'] or '', 'is_active': item['is_active'],
                },
            )
        counts['authorities'] = len(payload.get('authorities', []))

        for item in payload.get('divisions', []):
            CourtDivision.objects.update_or_create(
                id=item['id'],
                defaults={
                    'court_id': item['court_id'], 'name': item['name'],
                    'division_type': item['division_type'] or '', 'judge_name': item['judge_name'] or '',
                    'working_hours': item['working_hours'] or '', 'review_hours': item['review_hours'] or '',
                    'location_inside': item['location_inside'] or '', 'notes': item['notes'] or '',
                    'is_active': item['is_active'],
                },
            )
        counts['divisions'] = len(payload.get('divisions', []))

        for item in payload.get('entities', []):
            CourtEntity.objects.update_or_create(
                id=item['id'],
                defaults={
                    'division_id': item['division_id'], 'name': item['name'],
                    'entity_type': item['entity_type'] or '', 'job_title': item['job_title'] or '',
                    'job_grade': item['job_grade'] or '', 'phone': item['phone'] or '',
                    'notes': item['notes'] or '', 'is_active': item['is_active'], 'order': item['order'],
                },
            )
        counts['entities'] = len(payload.get('entities', []))

        self.stdout.write(self.style.SUCCESS(f'تمت مزامنة التصنيف الميداني: {counts}'))
