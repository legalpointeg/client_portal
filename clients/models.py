"""
client_portal/clients/models.py
--------------------------------
النسخة المصغّرة من قاعدة البيانات الخاصة ببوابة العميل المستقلة (client_portal).

قرار تصميم أساسي:
كل موديل هنا بياخد نفس الـ UUID (id) بتاع السجل المقابل له في lawfirm_portal
الأصلي. يعني مفيش "mapping table" منفصلة بين المشروعين - آلية المزامنة
هتستخدم نفس الـ id وقت الـ create/update (get_or_create / update_or_create
باستخدام id=... مش username أو أي حقل تاني). ده بيبسّط منطق المزامنة جدًا:
أي تحديث من lawfirm_portal بييجي بنفس الـ id المعروف مسبقًا.

ملاحظة مهمة (لسه مفتوحة): PowerOfAttorney في المشروع الأصلي مرتبط بـ
public.OnlineClient مش بـ accounts.User مباشرة. الافتراض الحالي (بطلب صريح
من صاحب المشروع) هو إن accounts.User هو مصدر بيانات العميل الوحيد، فالحقل
`client` هنا بيشاور على Client (المكافئ لـ accounts.User) - أي تعارض
فعلي هيظهر وقت كتابة سكريبت المزامنة نفسه ومحتاج قرار حينها.
"""
import uuid

from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import models


# ============================================================
# 1) Client — مكافئ accounts.models.User (role='client') فقط
# ============================================================
class Client(AbstractUser):
    """
    مستخدم بوابة العميل. بيورّث AbstractUser عشان نستفيد من نظام
    المصادقة الجاهز في Django (بدل ما نبني نظام دخول من الصفر)،
    لكن الحقول الإضافية هنا نفسها المستخدمة فعليًا في صفحات العميل
    الحالية (accounts.User في lawfirm_portal).
    """
    id = models.UUIDField(primary_key=True, editable=False)  # نفس id السجل الأصلي
    full_name = models.CharField('الاسم الكامل', max_length=200)
    phone = models.CharField('رقم الهاتف', max_length=20, blank=True)
    client_code = models.CharField('كود العميل', max_length=20, unique=True)
    national_id = models.CharField('الرقم القومي', max_length=20, blank=True, default='')
    birth_date = models.DateField('تاريخ الميلاد', null=True, blank=True)
    address = models.TextField('العنوان', blank=True)
    job = models.CharField('المهنة', max_length=100, blank=True)

    # وقت آخر مزامنة ناجحة لهذا السجل من lawfirm_portal (تشخيصي بحت)
    synced_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'عميل'
        verbose_name_plural = 'العملاء'

    def __str__(self):
        return f'{self.full_name} ({self.client_code})'


# ============================================================
# 2) Case — مكافئ cases.models.Case (حقول العرض فقط)
# ============================================================
class Case(models.Model):
    id = models.UUIDField(primary_key=True, editable=False)
    case_number = models.CharField('رقم القضية', max_length=100, unique=True)
    judicial_number = models.CharField('الرقم القضائي الرسمي', max_length=100, blank=True, default='')
    title = models.CharField('عنوان القضية', max_length=500)
    case_type = models.CharField('نوع القضية', max_length=30)
    court = models.CharField('المحكمة', max_length=200)
    circuit = models.CharField('الدائرة', max_length=100, blank=True)
    status = models.CharField('الحالة', max_length=20)
    opened_date = models.DateField('تاريخ فتح القضية')
    closed_date = models.DateField('تاريخ الإغلاق', null=True, blank=True)
    subject_matter = models.TextField('موضوع القضية', blank=True)
    tags = models.CharField('وسوم', max_length=500, blank=True)

    synced_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'قضية'
        verbose_name_plural = 'القضايا'

    def __str__(self):
        return self.title


# ============================================================
# 3) CasePortalLink — بيتحكم في رؤية العميل للقضية (محوري)
# ============================================================
class CasePortalLink(models.Model):
    id = models.UUIDField(primary_key=True, editable=False)
    case = models.ForeignKey(Case, on_delete=models.CASCADE, related_name='portal_links')
    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='case_links')
    is_visible_to_client = models.BooleanField('مرئي للعميل', default=False)
    shared_fields = models.JSONField('الحقول المشتركة مع العميل', default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'ربط قضية بعميل'
        verbose_name_plural = 'روابط القضايا بالعملاء'
        unique_together = ('case', 'client')

    def __str__(self):
        return f'{self.case} <-> {self.client}'


# ============================================================
# 4) Party — أطراف القضية
# ============================================================
class Party(models.Model):
    id = models.UUIDField(primary_key=True, editable=False)
    case = models.ForeignKey(Case, on_delete=models.CASCADE, related_name='parties')
    party_type = models.CharField('نوع الطرف', max_length=20)
    full_name = models.CharField('الاسم الكامل', max_length=300)
    organization = models.CharField('الجهة / المؤسسة', max_length=200, blank=True)
    national_id = models.CharField('الرقم الوطني / السجل', max_length=50, blank=True)
    phone = models.CharField('الهاتف', max_length=20, blank=True)
    email = models.EmailField(blank=True)
    address = models.TextField('العنوان', blank=True)
    notes = models.TextField('ملاحظات', blank=True)

    class Meta:
        verbose_name = 'طرف'
        verbose_name_plural = 'أطراف القضايا'

    def __str__(self):
        return self.full_name


# ============================================================
# 5) ClientFile + FileComment — مستندات العميل
# ============================================================
class ClientFile(models.Model):
    id = models.UUIDField(primary_key=True, editable=False)
    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='files')
    file_type = models.CharField('نوع الملف', max_length=20)
    uploaded_by = models.CharField('رُفع بواسطة', max_length=10)
    display_name = models.CharField('الاسم', max_length=255)
    folder_name = models.CharField('المجلد الفرعي', max_length=255, blank=True, default='')
    # الملف نفسه مش هيتخزن محليًا - رابط Google Drive هو المصدر (زي الأصلي)
    gdrive_url = models.URLField('رابط Google Drive', blank=True)
    is_visible = models.BooleanField('مرئي للعميل', default=True)
    admin_comment = models.TextField('تعليق الأدمن', blank=True)
    file_size = models.PositiveIntegerField('حجم الملف (bytes)', default=0)
    created_at = models.DateTimeField('تاريخ الرفع')

    # ============================================================
    # حقول الفهرس الإداري (مضافة بدون كسر أي شيء قائم) —
    # id أعلاه يبقى هو المعرّف الثابت دايمًا (لا يتغير أبدًا).
    # display_name = الاسم المعروض/القابل للتعديل من الفهرس.
    # original_name = الاسم الأصلي وقت الرفع (لا يتغير أبدًا، توثيقي فقط).
    # folder_name أعلاه = "المجموعة" (نفس الحقل القديم، بدون تغيير معناه).
    # order_index = ترتيب العرض *داخل* نفس المجموعة، مستقل عن id والاسم.
    # ============================================================
    original_name = models.CharField('الاسم الأصلي وقت الرفع', max_length=255, blank=True, default='')
    order_index = models.PositiveIntegerField('ترتيب العرض داخل المجموعة', default=0)
    ocr_text = models.TextField('نص OCR المستخرج', blank=True, default='')
    ocr_status = models.CharField(
        'حالة OCR', max_length=20, default='not_run',
        choices=[
            ('not_run', 'لم تتم بعد'),
            ('processing', 'جارٍ الاستخراج'),
            ('done', 'تم الاستخراج'),
            ('failed', 'فشل الاستخراج'),
            ('not_applicable', 'لا ينطبق (ليس صورة)'),
        ],
    )
    # نسخة من Drive file_id مخزّنة محليًا (بدل استخراجها من الرابط كل مرة) —
    # gdrive_url يبقى هو المرجع الأساسي دايمًا؛ ده كاش فقط لتسريع العمليات
    # (إعادة التسمية، تحديث المصغّرات...). لو فاضي، يتم استخراجه من الرابط كالمعتاد.
    gdrive_file_id = models.CharField('معرّف ملف Drive', max_length=100, blank=True, default='')

    class Meta:
        verbose_name = 'مستند عميل'
        verbose_name_plural = 'مستندات العملاء'
        ordering = ['folder_name', 'order_index', '-created_at']

    def __str__(self):
        return self.display_name


class FileComment(models.Model):
    id = models.UUIDField(primary_key=True, editable=False)
    file = models.ForeignKey(ClientFile, on_delete=models.CASCADE, related_name='comments')
    author_type = models.CharField('نوع الكاتب', max_length=10)
    text = models.TextField('نص التعليق')
    parent = models.ForeignKey('self', null=True, blank=True, on_delete=models.CASCADE, related_name='replies')
    created_at = models.DateTimeField('وقت التعليق', auto_now_add=True)

    class Meta:
        verbose_name = 'تعليق على مستند'
        verbose_name_plural = 'تعليقات المستندات'


# ============================================================
# 6) Invoice — الفواتير (عرض فقط، بدون منطق دفع)
# ============================================================
class Invoice(models.Model):
    id = models.UUIDField(primary_key=True, editable=False)
    case = models.ForeignKey(Case, on_delete=models.SET_NULL, null=True, blank=True, related_name='invoices')
    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='invoices')
    invoice_num = models.CharField('رقم الفاتورة', max_length=50, unique=True)
    issue_date = models.DateField('تاريخ الإصدار')
    due_date = models.DateField('تاريخ الاستحقاق', null=True, blank=True)
    amount = models.DecimalField('مبلغ الفاتورة', max_digits=12, decimal_places=2)
    tax_rate = models.DecimalField('نسبة الضريبة %', max_digits=5, decimal_places=2, default=0)
    status = models.CharField('الحالة', max_length=15)
    notes = models.TextField('ملاحظات', blank=True)

    class Meta:
        verbose_name = 'فاتورة'
        verbose_name_plural = 'الفواتير'

    def __str__(self):
        return self.invoice_num


# ============================================================
# 7) Consultation
# ============================================================
class Consultation(models.Model):
    id = models.UUIDField(primary_key=True, editable=False)
    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='consultations')
    subject = models.CharField('موضوع الاستشارة', max_length=300)
    question_text = models.TextField('نص الاستشارة')
    status = models.CharField('الحالة', max_length=20)
    admin_reply = models.TextField('رد المكتب', blank=True)
    replied_at = models.DateTimeField('تاريخ الرد', null=True, blank=True)
    is_urgent = models.BooleanField('عاجلة', default=False)
    created_at = models.DateTimeField('تاريخ الإرسال')

    class Meta:
        verbose_name = 'استشارة'
        verbose_name_plural = 'الاستشارات'

    def __str__(self):
        return self.subject


# ============================================================
# 8) Notification + ClientPopupMessage
# ============================================================
class Notification(models.Model):
    id = models.UUIDField(primary_key=True, editable=False)
    recipient = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='notifications')
    notif_type = models.CharField('النوع', max_length=20, default='general')
    title = models.CharField('العنوان', max_length=200)
    body = models.TextField('النص', blank=True)
    link = models.CharField('الرابط', max_length=500, blank=True)
    is_read = models.BooleanField('مقروء', default=False)
    created_at = models.DateTimeField()

    class Meta:
        verbose_name = 'إشعار'
        verbose_name_plural = 'الإشعارات'


class ClientPopupMessage(models.Model):
    id = models.UUIDField(primary_key=True, editable=False)
    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='popup_messages')
    case = models.ForeignKey(Case, on_delete=models.SET_NULL, null=True, blank=True, related_name='popup_messages')
    message_type = models.CharField('النوع', max_length=20, default='brochure')
    title = models.CharField('العنوان', max_length=200)
    body = models.TextField('النص', blank=True)
    link = models.CharField('الرابط', max_length=500, blank=True)
    priority = models.PositiveIntegerField('الأولوية', default=0)
    approved_by_admin = models.BooleanField('اعتماد الأدمن', default=False)
    approved_by_lawyer = models.BooleanField('اعتماد المحامي', default=False)
    dismissed_by_client = models.BooleanField('تم إخفاؤها من العميل', default=False)
    dismissed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField()

    class Meta:
        verbose_name = 'رسالة منبثقة للعميل'
        verbose_name_plural = 'الرسائل المنبثقة للعملاء'


# ============================================================
# 9) PowerOfAttorney
# ============================================================
class PowerOfAttorney(models.Model):
    """
    ⚠️ الأصل مرتبط بـ public.OnlineClient مش accounts.User مباشرة.
    الحقل client هنا افتراض مؤقت (accounts.User = المصدر الوحيد للعميل)
    محتاج تأكيد فعلي وقت كتابة سكريبت المزامنة - راجع الملاحظة أعلى الملف.
    """
    id = models.UUIDField(primary_key=True, editable=False)
    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='powers_of_attorney', null=True, blank=True)
    poa_type = models.CharField('نوع التوكيل', max_length=30, default='special')
    title = models.CharField('عنوان التوكيل', max_length=255)
    poa_number = models.CharField('رقم التوكيل', max_length=100, blank=True)
    issue_date = models.DateField('تاريخ الإصدار', null=True, blank=True)
    expiry_date = models.DateField('تاريخ الانتهاء', null=True, blank=True)
    notary_office = models.CharField('مكتب التوثيق', max_length=200, blank=True)
    visible_fields = models.JSONField('الحقول الظاهرة للعميل', default=list, blank=True)

    class Meta:
        verbose_name = 'توكيل'
        verbose_name_plural = 'التوكيلات'

    def __str__(self):
        return self.title


# ============================================================
# 10) Admin — مكافئ accounts.models.User (is_staff=True) فقط
# ============================================================
class Admin(models.Model):
    """
    نسخة عرض فقط من حسابات الأدمن في lawfirm_portal (is_staff=True).
    نفس فكرة Client: بياخد نفس id السجل الأصلي، بدون منطق دخول خاص بيه هنا.
    """
    id = models.UUIDField(primary_key=True, editable=False)
    username = models.CharField('اسم المستخدم', max_length=150)
    full_name = models.CharField('الاسم الكامل', max_length=200, blank=True)
    email = models.EmailField('البريد الإلكتروني', blank=True)
    phone = models.CharField('رقم الهاتف', max_length=20, blank=True)
    national_id = models.CharField('الرقم القومي', max_length=20, blank=True, default='')
    birth_date = models.DateField('تاريخ الميلاد', null=True, blank=True)
    address = models.TextField('العنوان', blank=True)
    job = models.CharField('المهنة', max_length=100, blank=True)
    is_active = models.BooleanField('نشط', default=True)
    password_hash = models.CharField('كلمة المرور (هاش)', max_length=255, blank=True)

    synced_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'أدمن'
        verbose_name_plural = 'الأدمن'

    def __str__(self):
        return f'{self.full_name or self.username}'
