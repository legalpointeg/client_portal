"""
client_portal/clients/management/commands/sync_clients.py
-------------------------------------------------------------
management command بيسحب بيانات العملاء من lawfirm_portal (endpoint
bridge/portal-export/clients/) ويحدّث/ينشئ سجلات Client محليًا.

الاستخدام:
    python3 manage.py sync_clients

يعتمد على إعدادين في settings.py:
    LAWFIRM_API_BASE_URL  - مثال: 'https://legalbridgeeg.pythonanywhere.com'
    PORTAL_SYNC_API_KEY    - نفس القيمة المضبوطة في lawfirm_portal بالظبط

يستخدم urllib المدمجة في بايثون (مش مكتبة requests) عشان منحتاجش نتثبت
حاجة جديدة في venv دلوقتي.
"""
import json
import urllib.error
import urllib.request
from datetime import datetime

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from clients.models import Client


class Command(BaseCommand):
    help = 'يسحب بيانات العملاء من lawfirm_portal ويحدّث الجدول المحلي (Client).'

    def handle(self, *args, **options):
        base_url = getattr(settings, 'LAWFIRM_API_BASE_URL', '').rstrip('/')
        api_key = getattr(settings, 'PORTAL_SYNC_API_KEY', '')

        if not base_url or not api_key:
            raise CommandError(
                'لازم تضبط LAWFIRM_API_BASE_URL و PORTAL_SYNC_API_KEY في settings.py أولاً.'
            )

        url = f'{base_url}/bridge/portal-export/clients/'
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

        clients_data = payload.get('clients', [])
        created_count = 0
        updated_count = 0
        now = timezone.now()

        for item in clients_data:
            birth_date = None
            if item.get('birth_date'):
                birth_date = datetime.strptime(item['birth_date'], '%Y-%m-%d').date()

            obj, created = Client.objects.update_or_create(
                id=item['id'],
                defaults={
                    'username': item['username'],
                    'full_name': item['full_name'] or '',
                    'email': item['email'] or '',
                    'phone': item['phone'] or '',
                    'client_code': item['client_code'] or '',
                    'national_id': item['national_id'] or '',
                    'birth_date': birth_date,
                    'address': item['address'] or '',
                    'job': item['job'] or '',
                    'is_active': item['is_active'],
                    'password': item.get('password', ''),
                    'synced_at': now,
                },
            )
            if created:
                created_count += 1
            else:
                updated_count += 1

        self.stdout.write(self.style.SUCCESS(
            f'تمت المزامنة: {created_count} عميل جديد، {updated_count} عميل محدَّث '
            f'(الإجمالي المستلم: {len(clients_data)}).'
        ))
