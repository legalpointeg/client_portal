"""
client_portal/clients/ocr_utils.py
-----------------------------------
استخراج نص OCR من الصور المرفوعة.

قرار تقني (اتخذته كخبير مسؤول، مع توضيح السبب صراحة لأنه قرار بنية تحتية
حقيقي وليس مجرد تفضيل أسلوب كود):

- PythonAnywhere لا يمنح صلاحية root/sudo على أي باقة (مجانية أو مدفوعة) -
  فمكتبة pytesseract (اللي محتاجة تثبيت tesseract كـ binary نظام عبر apt)
  غير قابلة للتشغيل هنا إطلاقًا، بغض النظر عن نوع الحساب.
- Google Cloud Vision API كان ممكن يشتغل، لكنه يحتاج تفعيل API منفصل
  ومحتمل فوترة منفصلة عن حساب Drive الحالي - قرار يحتاج تأكيدك أولًا لو
  حبينا نتحول له لاحقًا (جودة أعلى في المستندات المعقدة).
- الحل المُختار الآن: خاصية OCR المدمجة في Google Drive API نفسها
  (تحويل صورة إلى Google Doc مع ocrLanguage عند الرفع، ثم تصدير النص
  وحذف الملف المؤقت) - تستخدم *نفس* توكن Drive المُعد بالفعل في
  drive_utils.py، بدون أي اعتماد أو تكلفة إضافية. الجودة أبسط من
  Cloud Vision الكامل لكنها كافية لمعظم المستندات النصية الواضحة.

يمكن استبدال هذه الوحدة بـ Cloud Vision لاحقًا بسهولة لأن التوقيع
(extract_text_from_image) لا يتغير من ناحية الاستدعاء في views.py.
"""
import io
import logging

from googleapiclient.http import MediaIoBaseUpload, MediaIoBaseDownload
from googleapiclient.errors import HttpError

from .drive_utils import _get_drive_service, DRIVE_ROOT_FOLDER_ID, _get_or_create_folder

logger = logging.getLogger(__name__)

OCR_TEMP_FOLDER_NAME = '_ocr_temp'


def extract_text_from_image(image_bytes: bytes, mime_type: str, ocr_language: str = 'ar'):
    """
    يرفع الصورة مؤقتًا كـ Google Doc (بتحويل OCR تلقائي من Drive)، يستخرج
    النص، ثم يحذف الملف المؤقت فورًا - سواء نجحت العملية أو فشلت.

    يرجع (ocr_text, ok). لو ok=False، ocr_text = '' والسبب يتسجل في اللوج
    فقط (لا يوقف عملية الرفع الأساسية بأي حال).
    """
    service = None
    temp_file_id = None
    try:
        service = _get_drive_service()
        temp_folder_id = _get_or_create_folder(service, OCR_TEMP_FOLDER_NAME, DRIVE_ROOT_FOLDER_ID)

        media = MediaIoBaseUpload(io.BytesIO(image_bytes), mimetype=mime_type, resumable=False)
        file_metadata = {
            'name': 'ocr_temp',
            'mimeType': 'application/vnd.google-apps.document',
            'parents': [temp_folder_id],
        }
        created = service.files().create(
            body=file_metadata, media_body=media, fields='id',
            ocrLanguage=ocr_language,
        ).execute()
        temp_file_id = created['id']

        request = service.files().export_media(fileId=temp_file_id, mimeType='text/plain')
        buf = io.BytesIO()
        downloader = MediaIoBaseDownload(buf, request)
        done = False
        while not done:
            _, done = downloader.next_chunk()

        text = buf.getvalue().decode('utf-8', errors='replace').strip()
        return text, True

    except HttpError as e:
        logger.warning(f'[ocr_utils] فشل استخراج OCR عبر Drive: {e}')
        return '', False
    except Exception as e:
        logger.exception('[ocr_utils] خطأ غير متوقع أثناء استخراج OCR')
        return '', False
    finally:
        if service is not None and temp_file_id is not None:
            try:
                service.files().delete(fileId=temp_file_id).execute()
            except Exception:
                logger.warning(f'[ocr_utils] تعذّر حذف الملف المؤقت {temp_file_id} - قد يحتاج تنظيف يدوي لاحقًا')
