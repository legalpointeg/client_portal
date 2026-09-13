"""
client_portal/clients/management/commands/sync_sessions.py
-------------------------------------------------------------
management command بيسحب بيانات الجلسات من lawfirm_portal (endpoint
bridge/portal-export/sessions/) ويحدّث/ينشئ سجلات Session محليًا.

يعتمد على وجود القضية (Case) المرتبطة مسبقًا - لازم sync_cases يتشغل
قبله. أي جلسة قضيتها مش موجودة محليًا هيتم تجاهلها بدل ما يفشل الأمر كله.
"""
import json
import urllib.error
import urllib.request
from datetime import datetime

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from clients.models import Case, Session


class Command(BaseCommand):
    help = 'يسحب بيانات الجلسات من lawfirm_portal ويحدّث الجدول المحلي (Session).'

    def handle(self, *args, **options):
        base_url = getattr(settings, 'LAWFIRM_API_BASE_URL', '').rstrip('/')
        api_key = getattr(settings, 'PORTAL_SYNC_API_KEY', '')

        if not base_url or not api_key:
            raise CommandError(
                'لازم تضبط LAWFIRM_API_BASE_URL و PORTAL_SYNC_API_KEY في settings.py أولاً.'
            )

        url = f'{base_url}/bridge/portal-export/sessions/'
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

        sessions_data = payload.get('sessions', [])
        created_count = 0
        updated_count = 0
        skipped_count = 0
        now = timezone.now()

        def parse_date(value):
            return datetime.strptime(value, '%Y-%m-%d').date() if value else None

        def parse_time(value):
            return datetime.strptime(value, '%H:%M:%S').time() if value else None

        for item in sessions_data:
            try:
                case = Case.objects.get(id=item['case_id'])
            except Case.DoesNotExist:
                skipped_count += 1
                continue

            obj, created = Session.objects.update_or_create(
                id=item['id'],
                defaults={
                    'case': case,
                    'session_number': item['session_number'],
                    'session_date': parse_date(item['session_date']),
                    'session_time': parse_time(item['session_time']),
                    'location': item['location'] or '',
                    'result': item['result'] or '',
                    'minutes': item['minutes'] or '',
                    'ruling': item['ruling'] or '',
                    'next_session_date': parse_date(item['next_session_date']),
                    'postponement_reason': item['postponement_reason'] or '',
                    'requests': item['requests'] or '',
                    'permits': item['permits'] or '',
                    'preparations': item['preparations'] or '',
                    'obstacles': item['obstacles'] or '',
                    'tags': item['tags'] or '',
                    'is_visible_to_client': item['is_visible_to_client'],
                    'synced_at': now,
                },
            )
            if created:
                created_count += 1
            else:
                updated_count += 1

        self.stdout.write(self.style.SUCCESS(
            f'تمت مزامنة الجلسات: {created_count} جديدة، {updated_count} محدَّثة، '
            f'{skipped_count} متجاهَلة (قضية غير موجودة) '
            f'(الإجمالي المستلم: {len(sessions_data)}).'
        ))
