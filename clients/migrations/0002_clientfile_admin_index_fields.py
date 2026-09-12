"""
إضافة حقول الفهرس الإداري لـ ClientFile — بدون حذف أو تعديل أي حقل قديم.
تتضمن خطوة بيانات (data migration) لتعبئة original_name و order_index
للسجلات الموجودة بالفعل، حتى لا تحتاج الصور القديمة لإعادة رفع.
"""
from django.db import migrations, models


def backfill_existing_files(apps, schema_editor):
    ClientFile = apps.get_model('clients', 'ClientFile')

    # original_name: لو فاضي، ناخده من display_name الحالي (أفضل تقريب متاح
    # للاسم الأصلي بما إن الاسم الحقيقي وقت الرفع مش متخزن بشكل منفصل قبل كده).
    ClientFile.objects.filter(original_name='').update(original_name=models.F('display_name'))

    # order_index: نرتب الملفات القديمة داخل كل مجموعة (client, folder_name)
    # حسب created_at الحالي، عشان الترتيب المعروض النهاردة يفضل زي ما هو
    # بالظبط بعد الترقية (لا يوجد أي قفز أو اختلاط).
    from collections import defaultdict
    groups = defaultdict(list)
    for f in ClientFile.objects.all().order_by('client_id', 'folder_name', 'created_at'):
        groups[(f.client_id, f.folder_name)].append(f)

    for _, files in groups.items():
        for idx, f in enumerate(files):
            f.order_index = idx
            f.save(update_fields=['order_index'])


def noop_reverse(apps, schema_editor):
    # لا داعي للتراجع عن البيانات نفسها - فقط الحقول تُحذف تلقائيًا عند reverse.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('clients', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='clientfile',
            name='original_name',
            field=models.CharField(blank=True, default='', max_length=255, verbose_name='الاسم الأصلي وقت الرفع'),
        ),
        migrations.AddField(
            model_name='clientfile',
            name='order_index',
            field=models.PositiveIntegerField(default=0, verbose_name='ترتيب العرض داخل المجموعة'),
        ),
        migrations.AddField(
            model_name='clientfile',
            name='ocr_text',
            field=models.TextField(blank=True, default='', verbose_name='نص OCR المستخرج'),
        ),
        migrations.AddField(
            model_name='clientfile',
            name='ocr_status',
            field=models.CharField(
                choices=[
                    ('not_run', 'لم تتم بعد'),
                    ('processing', 'جارٍ الاستخراج'),
                    ('done', 'تم الاستخراج'),
                    ('failed', 'فشل الاستخراج'),
                    ('not_applicable', 'لا ينطبق (ليس صورة)'),
                ],
                default='not_run',
                max_length=20,
                verbose_name='حالة OCR',
            ),
        ),
        migrations.AddField(
            model_name='clientfile',
            name='gdrive_file_id',
            field=models.CharField(blank=True, default='', max_length=100, verbose_name='معرّف ملف Drive'),
        ),
        migrations.AlterModelOptions(
            name='clientfile',
            options={
                'ordering': ['folder_name', 'order_index', '-created_at'],
                'verbose_name': 'مستند عميل',
                'verbose_name_plural': 'مستندات العملاء',
            },
        ),
        migrations.RunPython(backfill_existing_files, noop_reverse),
    ]
