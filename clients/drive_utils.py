"""
client_portal/clients/drive_utils.py
-------------------------------------
وحدة رفع المستندات الموحّدة لـ Google Drive الخاصة ببوابة العميل المستقلة.

قرار معماري: نفس حساب/توكن Google Drive المستخدم في lawfirm_portal الأصلي،
لكن نسخة منفصلة من ملف التوكن مخزّنة محليًا على سيرفر client_portal
(secrets/owner_oauth_token.json) - مش endpoint حي بيطلب التوكن من
lawfirm_portal في كل مرة. ده بيحافظ على استقلالية المشروعين الكاملة:
لو lawfirm_portal وقع أو اتقفل السيرفر بتاعه، client_portal يفضل شغال
عادي لأنه معندوش أي اعتماد لحظي عليه.

نسخة الملف مرة واحدة يدويًا:
    cp /home/Lexpoint/lawfirm_portal/secrets/owner_oauth_token.json \
       /home/legalbridgeEG/client_portal/secrets/owner_oauth_token.json

كل سيرفر بعد كده بيعمل refresh لنسخته لوحده - الـ refresh_token بتاع
Google بيدعم أكتر من عميل (client) شغال بيه في نفس الوقت من غير تعارض.
"""
import io
import logging
import os

from django.conf import settings
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
import httplib2
import google_auth_httplib2
from googleapiclient.http import MediaIoBaseUpload, MediaIoBaseDownload
from googleapiclient.errors import HttpError

from .image_compress import compress_image_bytes

logger = logging.getLogger(__name__)

# نفس بنية المجلدات المستخدمة في lawfirm_portal الأصلي عشان لو حبينا
# نشوف الملفات القديمة والجديدة في نفس مكان Drive مفيش تعارض تسمية.
TOKEN_FILE = os.path.join(settings.BASE_DIR, 'secrets', 'owner_oauth_token.json')
SCOPES = ['https://www.googleapis.com/auth/drive']
CLIENTS_FOLDER_NAME = 'عملاء المكتب'
DRIVE_ROOT_FOLDER_ID = getattr(settings, 'DRIVE_ROOT_FOLDER_ID', None)


def _build_proxied_http():
    """
    يبني httplib2.Http مع إعدادات بروكسي صريحة لو السيرفر محتاج بروكسي
    خارجي (زي حسابات PythonAnywhere المجانية) - بيقرأ من متغيرات البيئة
    القياسية http_proxy / https_proxy.
    """
    proxy_url = os.environ.get('https_proxy') or os.environ.get('http_proxy')
    if not proxy_url:
        return httplib2.Http(timeout=60)

    cleaned = proxy_url.replace('http://', '').replace('https://', '').rstrip('/')
    if ':' in cleaned:
        host, port = cleaned.split(':', 1)
        port = int(port)
    else:
        host, port = cleaned, 3128

    proxy_info = httplib2.ProxyInfo(
        proxy_type=httplib2.socks.PROXY_TYPE_HTTP,
        proxy_host=host,
        proxy_port=port,
    )
    return httplib2.Http(proxy_info=proxy_info, timeout=60)


def _get_drive_service():
    """
    يبني اتصال Google Drive API من ملف التوكن المحلي، ويعمل refresh
    تلقائي لو الـ access token منتهي (باستخدام نفس الـ refresh_token).
    """
    creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        # نحفظ النسخة المحدّثة محليًا عشان مانعملش refresh زيادة عن اللزوم
        with open(TOKEN_FILE, 'w', encoding='utf-8') as f:
            f.write(creds.to_json())
    http = _build_proxied_http()
    authed_http = google_auth_httplib2.AuthorizedHttp(creds, http=http)
    return build('drive', 'v3', http=authed_http)


def _get_or_create_folder(service, folder_name, parent_id):
    """يدوّر على فولدر بالاسم ده جوه الأب، ولو مش موجود بيعمله."""
    safe_name = folder_name.replace("'", "\\'")
    query = (
        f"name = '{safe_name}' and mimeType = 'application/vnd.google-apps.folder' "
        f"and '{parent_id}' in parents and trashed = false"
    )
    results = service.files().list(q=query, fields='files(id, name)', spaces='drive').execute()
    files = results.get('files', [])
    if files:
        return files[0]['id']

    folder_metadata = {
        'name': folder_name,
        'mimeType': 'application/vnd.google-apps.folder',
        'parents': [parent_id],
    }
    folder = service.files().create(body=folder_metadata, fields='id').execute()
    return folder['id']


def upload_client_document(uploaded_file, client_full_name, doc_label, client_code=None, max_retries=5, upload_key=''):
    """
    رفع ملف واحد إلى Google Drive مع retry آمن + ضغط تلقائي للصور.
    نفس منطق lawfirm_portal.files_manager.client_drive_utils.upload_client_document
    بالظبط، عشان لو احتجنا نطابق سلوك الرفع بين المشروعين في المستقبل.

    يرجع dict فيه: ok, url, file_id, name, size (أو ok=False + message لو فشل).
    """
    try:
        service = _get_drive_service()
        clients_folder_id = _get_or_create_folder(service, CLIENTS_FOLDER_NAME, DRIVE_ROOT_FOLDER_ID)
        client_folder_id = _get_or_create_folder(service, client_full_name, clients_folder_id)

        # Idempotency: لو نفس upload_key اتبعت قبل كده، منرفعش نسخة تانية.
        if upload_key:
            safe_key = str(upload_key).replace("'", "\\'")
            q = (
                f"'{client_folder_id}' in parents and trashed=false "
                f"and appProperties has {{ key='upload_key' and value='{safe_key}' }}"
            )
            existing = service.files().list(
                q=q, fields='files(id,name,size)', spaces='drive', pageSize=1
            ).execute().get('files', [])
            if existing:
                ef = existing[0]
                return {
                    'ok': True,
                    'url': f"https://drive.google.com/file/d/{ef['id']}/view",
                    'file_id': ef['id'],
                    'name': ef.get('name', doc_label),
                    'size': int(ef.get('size') or 0),
                    'already_exists': True,
                }

        ext = ''
        original_name = getattr(uploaded_file, 'name', '') or ''
        if '.' in original_name:
            ext = '.' + original_name.rsplit('.', 1)[-1]
        filename = f"{doc_label}{ext}"

        file_bytes = uploaded_file.read()
        content_type = getattr(uploaded_file, 'content_type', None) or 'application/octet-stream'

        # ضغط الصور فقط - نفس إعداد MAX_DIMENSION / JPEG_QUALITY الموحّد
        upload_mimetype = content_type
        compressed_bytes = file_bytes
        if content_type and content_type.startswith('image/'):
            compressed_bytes, compressed_mime = compress_image_bytes(file_bytes)
            if compressed_mime:
                upload_mimetype = compressed_mime

        last_error = None
        for attempt in range(max_retries):
            try:
                buf = io.BytesIO(compressed_bytes)
                media = MediaIoBaseUpload(buf, mimetype=upload_mimetype, resumable=False)
                file_metadata = {
                    'name': filename,
                    'parents': [client_folder_id],
                }
                if upload_key:
                    file_metadata['appProperties'] = {'upload_key': str(upload_key)}

                file_meta = service.files().create(
                    body=file_metadata, media_body=media, fields='id,name,size'
                ).execute()

                return {
                    'ok': True,
                    'url': f"https://drive.google.com/file/d/{file_meta['id']}/view",
                    'file_id': file_meta['id'],
                    'name': file_meta.get('name', filename),
                    'size': int(file_meta.get('size') or 0),
                    'already_exists': False,
                }
            except HttpError as e:
                last_error = e
                logger.warning(f'[drive_utils] محاولة {attempt + 1} فشلت: {e}')
                continue

        return {'ok': False, 'message': f'فشل الرفع بعد {max_retries} محاولات: {last_error}'}

    except Exception as e:
        logger.exception('[drive_utils] خطأ غير متوقع أثناء الرفع')
        return {'ok': False, 'message': str(e)}


def extract_drive_file_id(url: str):
    """يستخرج file_id من رابط Google Drive - لازم يطابق نفس pattern الأصلي."""
    import re
    match = re.search(r'drive\.google\.com/file/d/([a-zA-Z0-9_-]+)', url or '')
    return match.group(1) if match else None


def rename_drive_file(file_id: str, new_filename: str):
    """
    يعيد تسمية ملف حقيقي على Google Drive بالـ file_id بتاعه.

    مهم (قاعدة عدم كسر الروابط - راجع التعليمات): إعادة التسمية في Drive
    لا تغيّر file_id ولا رابط /file/d/<id>/view القائم بأي شكل - فقط الاسم
    الظاهر يتغيّر. لذلك الفهرس مش محتاج يحدّث gdrive_url بعد نجاح هذه
    العملية؛ فقط display_name المحلي.

    يرجع dict: {'ok': True, 'name': الاسم الجديد الفعلي في Drive}
    أو {'ok': False, 'message': ...} لو فشلت العملية (مثلاً الملف اتحذف
    يدويًا من Drive، أو مشكلة صلاحيات) - في الحالة دي الفهرس المحلي يتحدث
    برضه لكن مع تسجيل حالة توضح إن المزامنة مع Drive فشلت.
    """
    try:
        service = _get_drive_service()
        updated = service.files().update(
            fileId=file_id,
            body={'name': new_filename},
            fields='id,name',
        ).execute()
        return {'ok': True, 'name': updated.get('name', new_filename)}
    except HttpError as e:
        logger.warning(f'[drive_utils] فشل إعادة تسمية الملف {file_id} على Drive: {e}')
        return {'ok': False, 'message': str(e)}
    except Exception as e:
        logger.exception('[drive_utils] خطأ غير متوقع أثناء إعادة التسمية على Drive')
        return {'ok': False, 'message': str(e)}


def download_file_bytes(file_id: str):
    """
    يرجّع بايتات الملف الحقيقي من Drive بنفس التوكن المصرّح بيه بالفعل
    (نفس آلية الرفع أعلاه، ونفس الآلية المستخدمة في ocr_utils.py).

    مهم: لازم نستخدم دي بدل رابط thumbnail العام (drive.google.com/thumbnail)
    وقت تضمين الصور في عرض_تفاعلي.html، لأن ملفات المكتب مش مشاركة عامة
    ("Anyone with the link") - رابط الـ thumbnail العام بيتطلب حساب Google
    مسجّل دخول وليه صلاحية، وطلب HTTP عادي من غير مصادقة بيرجّع صفحة تسجيل
    الدخول بتاعة Google نفسها بدل الصورة (وهو اللي كان بيحصل فعليًا).
    """
    service = _get_drive_service()
    request = service.files().get_media(fileId=file_id)
    buf = io.BytesIO()
    downloader = MediaIoBaseDownload(buf, request)
    done = False
    while not done:
        _, done = downloader.next_chunk()
    return buf.getvalue()
