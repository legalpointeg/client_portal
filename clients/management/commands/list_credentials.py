"""
client_portal/clients/management/commands/list_credentials.py
----------------------------------------------------------------
أمر لعرض بيانات دخول العملاء (username) + تعيين/طباعة باسورد دخول.

مهم جدًا (حقيقة تقنية، مش قرار تصميم): Django يخزّن الباسورد مُشفّر
(hash) دايمًا داخل قاعدة البيانات - مفيش أي طريقة لاسترجاع الباسورد
الأصلي القديم كما هو، حتى بالوصول المباشر لقاعدة البيانات. الممكن فقط
هو: (أ) معرفة الـusername، (ب) تعيين باسورد **جديد** وطباعته وقتها فقط
(لأنه اللحظة الوحيدة اللي بيكون فيها معروف كنص صريح قبل ما يتشفّر).

الاستخدام:
    python manage.py list_credentials
    python manage.py list_credentials --search "CLT-689470"
    python manage.py list_credentials --reset-username CLT-689470 --new-password "Xk9#mPz2Qw"
    python manage.py list_credentials --reset-username CLT-689470
"""
import secrets
import string

from django.core.management.base import BaseCommand
from django.contrib.auth.hashers import make_password

from clients.models import Client


def generate_random_password(length=12):
    alphabet = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(length))


class Command(BaseCommand):
    help = 'يعرض usernames العملاء، ويسمح بتعيين باسورد جديد لعميل معيّن (الباسورد القديم غير قابل للاسترجاع أبدًا).'

    def add_arguments(self, parser):
        parser.add_argument('--search', type=str, default=None,
            help='فلترة بالاسم الكامل أو client_code أو username (بحث جزئي)')
        parser.add_argument('--reset-username', type=str, default=None,
            help='username أو client_code بتاع العميل المطلوب تعيين باسورد جديد ليه')
        parser.add_argument('--new-password', type=str, default=None,
            help='الباسورد الجديد المطلوب (لو مش موجود، هيتولّد باسورد عشوائي قوي تلقائيًا)')

    def handle(self, *args, **options):
        if options['reset_username']:
            self._reset_password(options['reset_username'], options['new_password'])
            return

        qs = Client.objects.all().order_by('full_name')
        search = options['search']
        if search:
            qs = [
                c for c in qs
                if search.lower() in (c.username or '').lower()
                or search.lower() in (c.full_name or '').lower()
                or search.lower() in (c.client_code or '').lower()
            ]

        if not qs:
            self.stdout.write(self.style.WARNING('لا يوجد عملاء مطابقين.'))
            return

        self.stdout.write(self.style.NOTICE(
            'تنبيه: الباسوردات مُشفّرة في القاعدة ولا يمكن عرضها هنا - '
            'استخدم --reset-username لتعيين باسورد جديد لعميل معيّن.\n'
        ))
        self.stdout.write(f"{'username':<20} {'client_code':<15} {'full_name'}")
        self.stdout.write('-' * 70)
        for c in qs:
            self.stdout.write(f"{c.username:<20} {c.client_code:<15} {c.full_name}")

    def _reset_password(self, identifier, new_password):
        try:
            client = Client.objects.get(username=identifier)
        except Client.DoesNotExist:
            try:
                client = Client.objects.get(client_code=identifier)
            except Client.DoesNotExist:
                self.stdout.write(self.style.ERROR(f'لا يوجد عميل بهذا الـ username أو client_code: {identifier}'))
                return

        password = new_password or generate_random_password()
        client.password = make_password(password)
        client.save(update_fields=['password'])

        self.stdout.write(self.style.SUCCESS('تم تعيين باسورد جديد بنجاح.'))
        self.stdout.write(f"username : {client.username}")
        self.stdout.write(f"password : {password}")
        self.stdout.write(self.style.WARNING(
            'احتفظ بهذا الباسورد الآن - لن يظهر مرة أخرى بعد إغلاق هذه الشاشة.'
        ))
