"""
client_portal/clients/management/commands/sync_employees.py
-------------------------------------------------------------
management command بيسحب بيانات الموظفين من lawfirm_portal (endpoint
bridge/portal-export/employees/) ويحدّث/ينشئ سجلات Employee محليًا.

ملاحظة: id هنا integer عادي (مش UUID) مطابق لـ id الأصلي في employees.models.Employee.
"""
import json
import urllib.error
import urllib.request

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from clients.models import Employee


class Command(BaseCommand):
    help = 'يسحب بيانات الموظفين من lawfirm_portal ويحدّث الجدول المحلي (Employee).'

    def handle(self, *args, **options):
        base_url = getattr(settings, 'LAWFIRM_API_BASE_URL', '').rstrip('/')
        api_key = getattr(settings, 'PORTAL_SYNC_API_KEY', '')

        if not base_url or not api_key:
            raise CommandError(
                'لازم تضبط LAWFIRM_API_BASE_URL و PORTAL_SYNC_API_KEY في settings.py أولاً.'
            )

        url = f'{base_url}/bridge/portal-export/employees/'
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

        employees_data = payload.get('employees', [])
        created_count = 0
        updated_count = 0
        now = timezone.now()

        for item in employees_data:
            obj, created = Employee.objects.update_or_create(
                id=int(item['id']),
                defaults={
                    'employee_id': item['employee_id'] or '',
                    'name': item['name'] or '',
                    'role': item['role'] or '',
                    'sector_id': item['sector_id'],
                    'department_id': item['department_id'],
                    'bio': item['bio'] or '',
                    'phone': item['phone'] or '',
                    'email': item['email'] or '',
                    'is_active': item['is_active'],
                    'avatar_model': item['avatar_model'] or 'avatar_1',
                    'synced_at': now,
                },
            )
            if created:
                created_count += 1
            else:
                updated_count += 1

        self.stdout.write(self.style.SUCCESS(
            f'تمت مزامنة الموظفين: {created_count} جديد، {updated_count} محدَّث '
            f'(الإجمالي المستلم: {len(employees_data)}).'
        ))
