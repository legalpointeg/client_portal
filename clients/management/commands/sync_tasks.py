"""
client_portal/clients/management/commands/sync_tasks.py
-------------------------------------------------------------
management command بيسحب المهام (سريعة وتنفيذية) مع خطواتها وإجراءاتها
وتصنيفاتها من lawfirm_portal (endpoint bridge/portal-export/tasks/).

الترتيب: sync_task_taxonomy ثم sync_cases يجب أن يسبقا هذا الأمر.
أي مهمة قضيتها غير موجودة محليًا يتم تجاهلها بدل فشل الأمر كله.
"""
import json
import urllib.error
import urllib.request
from datetime import datetime

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from clients.models import (
    Case, Task, TaskStep, TaskAction,
    CaseSection, CourtSector, CourtAuthority, CourtDivision, CourtEntity,
)


class Command(BaseCommand):
    help = 'يسحب المهام مع خطواتها وإجراءاتها من lawfirm_portal.'

    def handle(self, *args, **options):
        base_url = getattr(settings, 'LAWFIRM_API_BASE_URL', '').rstrip('/')
        api_key = getattr(settings, 'PORTAL_SYNC_API_KEY', '')

        if not base_url or not api_key:
            raise CommandError('لازم تضبط LAWFIRM_API_BASE_URL و PORTAL_SYNC_API_KEY في settings.py أولاً.')

        url = f'{base_url}/bridge/portal-export/tasks/'
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

        def parse_date(value):
            return datetime.strptime(value, '%Y-%m-%d').date() if value else None

        tasks_data = payload.get('tasks', [])
        created_count = 0
        updated_count = 0
        skipped_count = 0
        now = timezone.now()

        # الجولة الأولى: إنشاء/تحديث كل المهام بدون linked_task (لتجنب مشاكل الترتيب)
        for item in tasks_data:
            try:
                case = Case.objects.get(id=item['case_id'])
            except Case.DoesNotExist:
                skipped_count += 1
                continue

            obj, created = Task.objects.update_or_create(
                id=item['id'],
                defaults={
                    'case': case,
                    'kind': item['kind'],
                    'title': item['title'] or '',
                    'status': item['status'] or '',
                    'due_date': parse_date(item['due_date']),
                    'notes': item['notes'] or '',
                    'created_at': parse_datetime(item['created_at']),
                    'updated_at': parse_datetime(item['updated_at']),
                    'session_id': item['session_id'],
                    'responsible_party': item['responsible_party'] or '',
                    'priority': item['priority'],
                    'budget': item['budget'],
                    'ai_suggested': item['ai_suggested'],
                    'client_id': item['client_id'] or '',
                    'synced_at': now,
                },
            )
            if created:
                created_count += 1
            else:
                updated_count += 1

            # ربط التصنيفات (M2M)
            obj.sections.set(CaseSection.objects.filter(id__in=item['section_ids']))
            obj.sectors.set(CourtSector.objects.filter(id__in=item['sector_ids']))
            obj.court_authorities.set(CourtAuthority.objects.filter(id__in=item['authority_ids']))
            obj.court_divisions.set(CourtDivision.objects.filter(id__in=item['division_ids']))
            obj.entities.set(CourtEntity.objects.filter(id__in=item['entity_ids']))

            # الخطوات والإجراءات
            for step_item in item.get('steps', []):
                step_obj, _ = TaskStep.objects.update_or_create(
                    id=step_item['id'],
                    defaults={
                        'task': obj,
                        'title': step_item['title'] or '',
                        'status': step_item['status'] or '',
                        'due_date': parse_date(step_item['due_date']),
                        'location': step_item['location'] or '',
                        'executor': step_item['executor'] or '',
                        'expense': step_item['expense'],
                        'notes': step_item['notes'] or '',
                        'order': step_item['order'],
                        'created_at': parse_datetime(step_item['created_at']),
                    },
                )
                for action_item in step_item.get('actions', []):
                    TaskAction.objects.update_or_create(
                        id=action_item['id'],
                        defaults={
                            'step': step_obj,
                            'title': action_item['title'] or '',
                            'type': action_item['type'] or 'action',
                            'is_done': action_item['is_done'],
                            'due_date': parse_date(action_item['due_date']),
                            'location': action_item['location'] or '',
                            'expense': action_item['expense'],
                            'notes': action_item['notes'] or '',
                            'order': action_item['order'],
                            'created_at': parse_datetime(action_item['created_at']),
                        },
                    )

        # الجولة الثانية: ربط linked_task بعد ما كل المهام بقت موجودة
        for item in tasks_data:
            if item.get('linked_task_id'):
                try:
                    obj = Task.objects.get(id=item['id'])
                    obj.linked_task_id = item['linked_task_id']
                    obj.save(update_fields=['linked_task'])
                except Task.DoesNotExist:
                    pass

        self.stdout.write(self.style.SUCCESS(
            f'تمت مزامنة المهام: {created_count} جديدة، {updated_count} محدَّثة، '
            f'{skipped_count} متجاهَلة (قضية غير موجودة) (الإجمالي: {len(tasks_data)}).'
        ))
