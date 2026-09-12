"""
client_portal/clients/views.py
--------------------------------
تسجيل دخول/خروج العميل + لوحة التحكم الأساسية.
يستخدم نظام المصادقة القياسي في Django (authenticate/login) لأن
Client وارِث من AbstractUser أصلاً (راجع models.py).
"""
from django.contrib.auth import authenticate, login as auth_login, logout as auth_logout
from django.utils import timezone
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect

from .models import (
    CasePortalLink, ClientFile, Invoice,
    Consultation, Notification, PowerOfAttorney,
)


def login_view(request):
    if request.user.is_authenticated:
        return redirect('clients:dashboard')

    error = None
    posted_username = ''

    if request.method == 'POST':
        posted_username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')

        user = authenticate(request, username=posted_username, password=password)
        if user is not None:
            if not user.is_active:
                error = 'هذا الحساب غير مفعّل حاليًا. برجاء التواصل مع المكتب.'
            else:
                auth_login(request, user)
                return redirect('clients:dashboard')
        else:
            error = 'اسم المستخدم أو كلمة المرور غير صحيحة.'

    return render(request, 'clients/login.html', {
        'error': error,
        'posted_username': posted_username,
    })


def logout_view(request):
    auth_logout(request)
    return redirect('clients:login')


@login_required(login_url='/login/')
def dashboard_view(request):
    client = request.user

    visible_links = CasePortalLink.objects.filter(
        client=client, is_visible_to_client=True
    ).select_related('case')
    cases = [link.case for link in visible_links]

    files = ClientFile.objects.filter(
        client=client, is_visible=True
    ).order_by('-created_at')[:10]

    invoices = Invoice.objects.filter(client=client).order_by('-issue_date')[:10]
    consultations = Consultation.objects.filter(client=client).order_by('-created_at')[:10]
    notifications = Notification.objects.filter(recipient=client).order_by('-created_at')[:10]
    unread_notifications_count = Notification.objects.filter(
        recipient=client, is_read=False
    ).count()
    powers_of_attorney = PowerOfAttorney.objects.filter(client=client)

    return render(request, 'clients/dashboard.html', {
        'client': client,
        'cases': cases,
        'files': files,
        'invoices': invoices,
        'consultations': consultations,
        'notifications': notifications,
        'unread_notifications_count': unread_notifications_count,
        'powers_of_attorney': powers_of_attorney,
    })


from django.shortcuts import get_object_or_404
from django.http import JsonResponse, FileResponse
from django.views.decorators.http import require_POST

from .models import Case, ClientPopupMessage


@login_required(login_url='/login/')
def cases_list_view(request):
    client = request.user
    links = CasePortalLink.objects.filter(
        client=client, is_visible_to_client=True
    ).select_related('case').order_by('-case__opened_date')

    return render(request, 'clients/cases_list.html', {
        'links': links,
    })


@login_required(login_url='/login/')
def case_detail_view(request, case_id):
    client = request.user
    link = get_object_or_404(
        CasePortalLink,
        case_id=case_id, client=client, is_visible_to_client=True
    )
    case = link.case
    parties = case.parties.all()
    files = ClientFile.objects.filter(client=client, is_visible=True).order_by('-created_at')
    for f in files:
        _attach_drive_display_fields(f)
    invoices = Invoice.objects.filter(client=client, case=case).order_by('-issue_date')

    return render(request, 'clients/case_detail.html', {
        'link': link,
        'case': case,
        'parties': parties,
        'files': files,
        'invoices': invoices,
        'shared_fields': link.shared_fields,
    })


def _attach_drive_display_fields(f):
    """
    يحسب is_image/thumb_url/full_url لعنصر ClientFile واحد، ويكتب
    gdrive_file_id مرة واحدة في القاعدة لو كان فاضيًا (كاش، بدون تأثير
    على gdrive_url اللي يفضل هو المرجع الأساسي دايمًا).
    نفس المنطق المستخدم في case_detail_view وfiles_list_view قبل التوحيد،
    بدون أي تغيير في القيم الناتجة.
    """
    file_id = f.gdrive_file_id or extract_drive_file_id(f.gdrive_url)
    if file_id and not f.gdrive_file_id:
        f.gdrive_file_id = file_id
        f.save(update_fields=['gdrive_file_id'])
    f.is_image = (f.file_type == 'image' and bool(file_id))
    if f.is_image:
        f.thumb_url = f'https://drive.google.com/thumbnail?id={file_id}&sz=w400'
        f.full_url = f'https://drive.google.com/thumbnail?id={file_id}&sz=w1600'
    return f


@login_required(login_url='/login/')
def files_list_view(request):
    client = request.user
    files = ClientFile.objects.filter(
        client=client, is_visible=True
    ).order_by('folder_name', 'order_index', '-created_at')

    folders = {}
    for f in files:
        _attach_drive_display_fields(f)
        folders.setdefault(f.folder_name or 'عام', []).append(f)

    return render(request, 'clients/files_list.html', {
        'folders': folders,
    })


# ============================================================
# الفهرس الإداري (admin index) — زر عائم فوق صفحة "مستنداتي" الحالية.
# لا يغيّر أي سلوك قديم؛ فقط endpoints جديدة تخدم اللوحة الجانبية.
# ============================================================
import json


@login_required(login_url='/login/')
def files_index_data_view(request):
    """يرجع JSON بكل ملفات العميل (المرئية) لعرضها في لوحة الفهرس العائمة."""
    client = request.user
    files = ClientFile.objects.filter(
        client=client, is_visible=True
    ).order_by('folder_name', 'order_index', '-created_at')

    data = []
    for f in files:
        _attach_drive_display_fields(f)
        data.append({
            'id': str(f.id),
            'order_index': f.order_index,
            'display_name': f.display_name,
            'original_name': f.original_name,
            'folder_name': f.folder_name or 'عام',
            'is_image': f.is_image,
            'thumb_url': getattr(f, 'thumb_url', ''),
            'full_url': getattr(f, 'full_url', ''),
            'gdrive_url': f.gdrive_url,
            'ocr_text': f.ocr_text,
            'ocr_status': f.ocr_status,
            'status': 'مرئي' if f.is_visible else 'مخفي',
            'created_at': f.created_at.strftime('%Y-%m-%d %H:%M') if f.created_at else '',
        })

    groups_order = list(dict.fromkeys([d['folder_name'] for d in data]))
    return JsonResponse({'files': data, 'groups': groups_order})


@login_required(login_url='/login/')
@require_POST
def file_rename_view(request, file_id):
    """
    تعديل الاسم المعروض من الفهرس. الـ id لا يتغيّر أبدًا (هوية الصورة).
    يحاول أيضًا مزامنة الاسم الجديد إلى Google Drive نفسه (نفس الملف
    الحقيقي، بنفس file_id ونفس الرابط - راجع drive_utils.rename_drive_file)
    - لو فشلت مزامنة Drive، الاسم المحلي يتحدث برضه ويُرجع تحذير للواجهة
    بدل ما نمنع العملية بالكامل.
    """
    client = request.user
    f = get_object_or_404(ClientFile, id=file_id, client=client)

    try:
        payload = json.loads(request.body or '{}')
    except ValueError:
        payload = request.POST

    new_name = (payload.get('display_name') or '').strip()
    if not new_name:
        return JsonResponse({'ok': False, 'message': 'الاسم لا يمكن أن يكون فارغًا'}, status=400)

    old_name = f.display_name
    f.display_name = new_name
    f.save(update_fields=['display_name'])

    drive_warning = None
    file_id_drive = f.gdrive_file_id or extract_drive_file_id(f.gdrive_url)
    if file_id_drive:
        # نحافظ على نفس الامتداد الأصلي في Drive حتى لا تتلف صيغة الملف.
        ext = ''
        if '.' in old_name:
            ext = ''  # الاسم المعروض هنا اسم عرض فقط، الامتداد الحقيقي محفوظ داخل filename في Drive نفسه
        drive_result = rename_drive_file(file_id_drive, new_name)
        if not drive_result.get('ok'):
            drive_warning = 'تم تحديث الاسم محليًا، لكن تعذّرت مزامنته مع Google Drive.'

    return JsonResponse({
        'ok': True,
        'id': str(f.id),
        'display_name': f.display_name,
        'warning': drive_warning,
    })


@login_required(login_url='/login/')
@require_POST
def file_move_group_view(request, file_id):
    """نقل صورة لمجموعة (folder_name) تانية - الـ id يفضل ثابت زي ما هو."""
    client = request.user
    f = get_object_or_404(ClientFile, id=file_id, client=client)

    try:
        payload = json.loads(request.body or '{}')
    except ValueError:
        payload = request.POST

    new_group = (payload.get('folder_name') or '').strip()
    f.folder_name = new_group
    # لما تتنقل لمجموعة جديدة، تتحط آخر واحدة فيها افتراضيًا
    max_order = ClientFile.objects.filter(
        client=client, folder_name=new_group
    ).order_by('-order_index').values_list('order_index', flat=True).first()
    f.order_index = (max_order or 0) + 1
    f.save(update_fields=['folder_name', 'order_index'])

    return JsonResponse({'ok': True, 'id': str(f.id), 'folder_name': f.folder_name})


@login_required(login_url='/login/')
@require_POST
def file_reorder_view(request):
    """
    إعادة ترتيب مجموعة من الملفات داخل نفس المجموعة (drag/up-down).
    البيانات المتوقعة: {"order": [{"id": "...", "order_index": 0}, ...]}
    الترتيب مستقل تمامًا عن id وعن الاسم (راجع القاعدة الأساسية بالتعليمات).
    """
    client = request.user
    try:
        payload = json.loads(request.body or '{}')
    except ValueError:
        return JsonResponse({'ok': False, 'message': 'بيانات غير صالحة'}, status=400)

    order = payload.get('order') or []
    updated = 0
    for item in order:
        try:
            ClientFile.objects.filter(
                id=item['id'], client=client
            ).update(order_index=int(item['order_index']))
            updated += 1
        except (KeyError, ValueError, TypeError):
            continue

    return JsonResponse({'ok': True, 'updated': updated})


@login_required(login_url='/login/')
def invoices_list_view(request):
    client = request.user
    invoices = Invoice.objects.filter(client=client).order_by('-issue_date')

    return render(request, 'clients/invoices_list.html', {
        'invoices': invoices,
    })


@login_required(login_url='/login/')
def consultations_list_view(request):
    client = request.user
    consultations = Consultation.objects.filter(client=client).order_by('-created_at')

    return render(request, 'clients/consultations_list.html', {
        'consultations': consultations,
    })


@login_required(login_url='/login/')
def consultation_create_view(request):
    client = request.user

    if request.method == 'POST':
        subject = request.POST.get('subject', '').strip()
        question_text = request.POST.get('question_text', '').strip()
        is_urgent = request.POST.get('is_urgent') == 'on'

        if subject and question_text:
            import uuid as uuid_lib
            Consultation.objects.create(
                id=uuid_lib.uuid4(),
                client=client,
                subject=subject,
                question_text=question_text,
                status='pending',
                is_urgent=is_urgent,
                created_at=timezone.now(),
            )
            return redirect('clients:consultations_list')

    return render(request, 'clients/consultation_form.html')


@login_required(login_url='/login/')
@require_POST
def notification_mark_read_view(request, notif_id):
    client = request.user
    notif = get_object_or_404(Notification, id=notif_id, recipient=client)
    notif.is_read = True
    notif.save(update_fields=['is_read'])
    return JsonResponse({'ok': True})


import uuid as uuid_lib
import logging
from .drive_utils import upload_client_document, extract_drive_file_id, rename_drive_file, download_file_bytes
from .ocr_utils import extract_text_from_image
from .utils_ocr import build_docx, build_html

logger = logging.getLogger(__name__)


@login_required(login_url='/login/')
def bundle_upload_view(request):
    client = request.user

    if request.method == 'POST':
        folder_name = request.POST.get('folder_name', '').strip()
        uploaded_files = request.FILES.getlist('files')

        results = []
        for f in uploaded_files:
            file_id = uuid_lib.uuid4()
            base_name = f.name.rsplit('.', 1)[0] if '.' in f.name else f.name
            doc_label = f"{base_name}_{file_id.hex[:8]}"

            upload_result = upload_client_document(
                uploaded_file=f,
                client_full_name=client.full_name,
                doc_label=doc_label,
                client_code=client.client_code,
                upload_key=str(file_id),
            )

            if upload_result.get('ok'):
                is_image = (f.content_type or '').startswith('image/')
                max_order = ClientFile.objects.filter(
                    client=client, folder_name=folder_name
                ).order_by('-order_index').values_list('order_index', flat=True).first()

                ocr_text, ocr_status = '', 'not_applicable'
                if is_image:
                    try:
                        f.seek(0)
                        image_bytes = f.read()
                        ocr_text, ocr_ok = extract_text_from_image(image_bytes, f.content_type or 'image/jpeg')
                        ocr_status = 'done' if ocr_ok else 'failed'
                    except Exception:
                        logger.exception('[bundle_upload_view] فشل غير متوقع أثناء محاولة استخراج OCR')
                        ocr_status = 'failed'

                ClientFile.objects.create(
                    id=file_id,
                    client=client,
                    file_type='image' if is_image else 'other',
                    uploaded_by='client',
                    display_name=f.name,
                    original_name=f.name,
                    folder_name=folder_name,
                    gdrive_url=upload_result['url'],
                    gdrive_file_id=upload_result.get('file_id', ''),
                    order_index=(max_order or 0) + 1,
                    ocr_text=ocr_text,
                    ocr_status=ocr_status,
                    is_visible=True,
                    file_size=upload_result.get('size', 0),
                    created_at=timezone.now(),
                )
                results.append({'name': f.name, 'ok': True})
            else:
                results.append({
                    'name': f.name, 'ok': False,
                    'error': upload_result.get('message', ''),
                })

        return render(request, 'clients/bundle_upload_result.html', {'results': results})

    return render(request, 'clients/bundle_upload.html')


# ============================================================
# تجميع المجلد (bundle download) — manifest.json + Word + HTML
# تفاعلي + ملفات OCR منفصلة، الكل مضغوط في ZIP واحد.
# بدون أي مكتبة خارجية: zipfile, tempfile, json كلها من مكتبة بايثون
# القياسية فقط (build_docx و build_html في utils_ocr.py برضه stdlib بحت).
# ============================================================
import os
import re
import shutil
import tempfile
import zipfile
from django.db.models import Q

MAX_BUNDLE_SIZE = 200 * 1024 * 1024  # 200MB


def _safe_bundle_name(name):
    """يشيل أي حرف ممكن يسبب مشكلة في اسم ملف التحميل (بدون تأثير على folder_name في القاعدة)."""
    cleaned = re.sub(r'[\\/:"*?<>|\r\n]+', '_', name or 'مجلد').strip()
    return cleaned or 'مجلد'


@login_required(login_url='/login/')
def folder_bundle_download(request, folder_name):
    """
    يجمّع كل ملفات مجلد معيّن (يخص المستخدم الحالي فقط) في ZIP واحد فيه:
    manifest.json, النصوص_مجمعة.docx, عرض_تفاعلي.html, و<رقم>_ocr.txt
    لكل ملف. لا يعدّل أي شيء في القاعدة ولا في الصور الأصلية.
    """
    client = request.user

    # ملاحظة مهمة: في files_list_view، الملفات اللي folder_name بتاعها فاضي
    # بتتعرض تحت اسم "عام" (f.folder_name or 'عام') بس بدون ما تتغيّر فعليًا
    # في القاعدة. يعني لو الطلب جالنا على "عام"، لازم نجيب الفاضي زي الحرفي.
    if folder_name == 'عام':
        folder_filter = Q(folder_name='') | Q(folder_name='عام')
    else:
        folder_filter = Q(folder_name=folder_name)

    files = list(
        ClientFile.objects.filter(
            folder_filter, client=client, is_visible=True
        ).order_by('order_index', '-created_at')
    )

    if not files:
        return JsonResponse(
            {'ok': False, 'message': 'هذا المجلد فارغ أو غير موجود.'}, status=404
        )

    entries = []
    for i, f in enumerate(files, start=1):
        _attach_drive_display_fields(f)
        image_bytes = b''
        if getattr(f, 'is_image', False) and f.gdrive_file_id:
            try:
                image_bytes = download_file_bytes(f.gdrive_file_id)
            except Exception:
                logger.warning(
                    '[folder_bundle_download] تعذّر تحميل صورة الملف %s من Drive', f.id
                )
        entries.append({
            'index': i,
            'image_filename': f.display_name,
            'image_bytes': image_bytes,
            'text_path': f'{i:03d}_ocr.txt',
            'text': f.ocr_text,
        })

    tmp_dir = tempfile.mkdtemp(prefix='bundle_')
    try:
        # manifest.json فهرس نصي بس - من غير بايتات الصور (تفضل فاضية هنا
        # عمدًا) عشان الملف يفضل صغير وقابل للقراءة، لا علاقة له بحجم
        # عرض_تفاعلي.html.
        manifest_entries = [
            {k: v for k, v in entry.items() if k != 'image_bytes'}
            for entry in entries
        ]
        manifest_path = os.path.join(tmp_dir, 'manifest.json')
        with open(manifest_path, 'w', encoding='utf-8') as fh:
            json.dump(manifest_entries, fh, ensure_ascii=False, indent=2)

        docx_path = os.path.join(tmp_dir, 'النصوص_مجمعة.docx')
        build_docx(entries, docx_path, folder_name)

        html_path = os.path.join(tmp_dir, 'عرض_تفاعلي.html')
        build_html(entries, html_path, folder_name)

        safe_name = _safe_bundle_name(folder_name)
        zip_path = os.path.join(tmp_dir, f'{safe_name}_bundle.zip')
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            zf.write(manifest_path, 'manifest.json')
            zf.write(docx_path, 'النصوص_مجمعة.docx')
            zf.write(html_path, 'عرض_تفاعلي.html')
            for i, f in enumerate(files, start=1):
                zf.writestr(f'{i:03d}_ocr.txt', f.ocr_text or '')

        if os.path.getsize(zip_path) > MAX_BUNDLE_SIZE:
            shutil.rmtree(tmp_dir, ignore_errors=True)
            return JsonResponse(
                {'ok': False, 'message': 'حجم ملفات هذا المجلد أكبر من الحد المسموح (200MB).'},
                status=413,
            )

        opened_zip = open(zip_path, 'rb')
        response = FileResponse(opened_zip, content_type='application/zip')
        response['Content-Disposition'] = f'attachment; filename="{safe_name}_bundle.zip"'

        # تنظيف المجلد المؤقت بعد ما الإرسال يخلص فعليًا (FileResponse بيبعت
        # الملف بالـ streaming بعد ما الـ view يرجع، فمينفعش نمسح المجلد فورًا هنا).
        original_close = response.close

        def _cleanup_and_close():
            try:
                original_close()
            finally:
                shutil.rmtree(tmp_dir, ignore_errors=True)

        response.close = _cleanup_and_close
        return response

    except Exception:
        shutil.rmtree(tmp_dir, ignore_errors=True)
        logger.exception('[folder_bundle_download] فشل غير متوقع أثناء تجميع المجلد "%s"', folder_name)
        return JsonResponse(
            {'ok': False, 'message': 'حصل خطأ أثناء تجهيز الملف. حاول مرة أخرى.'}, status=500
        )
