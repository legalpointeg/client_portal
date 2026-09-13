"""
client_portal/clients/management/commands/sync_admins.py
-------------------------------------------------------------
management command بيسحب بيانات الأدمن من lawfirm_portal (endpoint
bridge/portal-export/admins/) ويحدّث/ينشئ سجلات Admin محليًا.

نفس فكرة sync_clients.py بالظبط - نفس settings المستخدمة
(LAWFIRM_API_BASE_URL, PORTAL_SYNC_API_KEY).
"""
import json
import urllib.error
import urllib.request
from datetime import datetime

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from clients.models import Admin


class Command(BaseCommand):
    help = 'يسحب بيانات الأدمن من lawfirm_portal ويحدّث الجدول المحلي (Admin).'

    def handle(self, *args, **options):
        base_url = getattr(settings, 'LAWFIRM_API_BASE_URL', '').rstrip('/')
        api_key = getattr(settings, 'PORTAL_SYNC_API_KEY', '')

        if not base_url or not api_key:
            raise CommandError(
                'لازم تضبط LAWFIRM_API_BASE_URL و PORTAL_SYNC_API_KEY في settings.py أولاً.'
            )

        url = f'{base_url}/bridge/portal-export/admins/'
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

        admins_data = payload.get('admins', [])
        created_count = 0
        updated_count = 0
        now = timezone.now()

        for item in admins_data:
            birth_date = None
            if item.get('birth_date'):
                birth_date = datetime.strptime(item['birth_date'], '%Y-%m-%d').date()

            obj, created = Admin.objects.update_or_create(
                id=item['id'],
                defaults={
                    'username': item['username'],
                    'full_name': item['full_name'] or '',
                    'email': item['email'] or '',
                    'phone': item['phone'] or '',
                    'national_id': item['national_id'] or '',
                    'birth_date': birth_date,
                    'address': item['address'] or '',
                    'job': item['job'] or '',
                    'is_active': item['is_active'],
                    'password_hash': item.get('password', ''),
                    'synced_at': now,
                },
            )
            if created:
                created_count += 1
            else:
                updated_count += 1

        self.stdout.write(self.style.SUCCESS(
            f'تمت مزامنة الأدمن: {created_count} جديد، {updated_count} محدَّث '
            f'(الإجمالي المستلم: {len(admins_data)}).'
        ))
