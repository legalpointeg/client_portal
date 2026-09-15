"""
client_portal/client_portal/urls.py
-------------------------------------
الـ URLs الرئيسية للمشروع. الـ routes الفعلية لصفحات العميل هتتضاف
في clients/urls.py لما نكتب الـ views (الخطوة الجاية بعد ده).
"""
from django.contrib import admin
from django.urls import path, include
from uploads import views as upload_views
from clients import bridge_export_views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('uploads/health/', upload_views.health_check, name='uploads_health'),
    path('webhook/upload-received', upload_views.receive_upload, name='receive_upload'),
    path('uploads/<str:client_id>', upload_views.list_client_uploads, name='list_client_uploads'),
    path('bridge/pending-consultations/', bridge_export_views.pending_consultations, name='pending_consultations'),
    path('bridge/mark-consultations-synced/', bridge_export_views.mark_consultations_synced, name='mark_consultations_synced'),
    path('', include('clients.urls')),
]
