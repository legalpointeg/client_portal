from django.urls import path

from . import views

urlpatterns = [
    path("", views.health_check, name="health_check"),
    path("webhook/upload-received", views.receive_upload, name="receive_upload"),
    path("uploads/<str:client_id>", views.list_client_uploads, name="list_client_uploads"),
]
