from django.db import models


class ClientUpload(models.Model):
    client_id = models.CharField(max_length=255)
    file_name = models.CharField(max_length=500)
    drive_url = models.URLField(max_length=1000)
    uploaded_at = models.DateTimeField()
    received_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.client_id} - {self.file_name}"
