"""
client_portal/clients/urls.py
-------------------------------
"""
from django.urls import path
from . import views

app_name = 'clients'

urlpatterns = [
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('', views.dashboard_view, name='dashboard'),

    path('cases/', views.cases_list_view, name='cases_list'),
    path('cases/<uuid:case_id>/', views.case_detail_view, name='case_detail'),

    path('files/', views.files_list_view, name='files_list'),

    path('invoices/', views.invoices_list_view, name='invoices_list'),

    path('consultations/', views.consultations_list_view, name='consultations_list'),
    path('consultations/new/', views.consultation_create_view, name='consultation_create'),

    path('notifications/<uuid:notif_id>/read/', views.notification_mark_read_view, name='notification_read'),
    path('files/upload/', views.bundle_upload_view, name='bundle_upload'),

    # الفهرس الإداري (زر عائم فوق صفحة "مستنداتي" الحالية) — جديد بالكامل،
    # لا يعدّل أي مسار قديم قائم أعلاه.
    path('files/index-data/', views.files_index_data_view, name='files_index_data'),
    path('files/<uuid:file_id>/rename/', views.file_rename_view, name='file_rename'),
    path('files/<uuid:file_id>/move-group/', views.file_move_group_view, name='file_move_group'),
    path('files/reorder/', views.file_reorder_view, name='file_reorder'),

    # تجميع المجلد (ZIP: manifest + Word + HTML تفاعلي + نصوص OCR) — جديد
    # بالكامل، لا يعدّل أي مسار قائم أعلاه.
    path('folders/<str:folder_name>/bundle/', views.folder_bundle_download, name='folder_bundle_download'),
]
