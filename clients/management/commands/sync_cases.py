"""
client_portal/clients/management/commands/sync_cases.py
-------------------------------------------------------------
management command بيسحب بيانات القضايا من lawfirm_portal (endpoint
bridge/portal-export/cases/) ويحدّث/ينشئ سجلات Case محليًا.
"""
import json
import urllib.error
import urllib.request
from datetime import datetime

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from clients.models import Case


class Command(BaseCommand):
    help = 'يسحب بيانات القضايا من lawfirm_portal ويحدّث الجدول المحلي (Case).'

    def handle(self, *args, **options):
        base_url = getattr(settings, 'LAWFIRM_API_BASE_URL', '').rstrip('/')
        api_key = getattr(settings, 'PORTAL_SYNC_API_KEY', '')

        if not base_url or not api_key:
            raise CommandError(
                'لازم تضبط LAWFIRM_API_BASE_URL و PORTAL_SYNC_API_KEY في settings.py أولاً.'
            )

        url = f'{base_url}/bridge/portal-export/cases/'
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

        cases_data = payload.get('cases', [])
        created_count = 0
        updated_count = 0
        now = timezone.now()

        def parse_date(value):
            return datetime.strptime(value, '%Y-%m-%d').date() if value else None

        for item in cases_data:
            obj, created = Case.objects.update_or_create(
                id=item['id'],
                defaults={
                    'case_number': item['case_number'] or '',
                    'judicial_number': item['judicial_number'] or '',
                    'title': item['title'] or '',
                    'case_type': item['case_type'] or '',
                    'court': item['court'] or '',
                    'circuit': item['circuit'] or '',
                    'status': item['status'] or '',
                    'opened_date': parse_date(item['opened_date']),
                    'closed_date': parse_date(item['closed_date']),
                    'subject_matter': item['subject_matter'] or '',
                    'tags': item['tags'] or '',
                    'synced_at': now,
                },
            )
            if created:
                created_count += 1
            else:
                updated_count += 1

        self.stdout.write(self.style.SUCCESS(
            f'تمت مزامنة القضايا: {created_count} جديدة، {updated_count} محدَّثة '
            f'(الإجمالي المستلم: {len(cases_data)}).'
        ))
