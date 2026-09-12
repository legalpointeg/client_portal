"""
clients/middleware.py
----------------------
Middleware بيشغّل sync_clients في الخلفية تلقائيًا مع كل طلب،
لكن بحد أدنى 5 دقايق بين كل تشغيل والتاني عشان ميحملش السيرفر.
"""
import threading
import time

from django.core.management import call_command

_lock = threading.Lock()
_last_sync_time = [0.0]
SYNC_COOLDOWN_SECONDS = 300  # 5 دقايق


def _run_sync():
    try:
        call_command('sync_clients')
    except Exception:
        # لو حصل خطأ (مثلاً السيرفر المصدر مش متاح مؤقتًا)، نتجاهله
        # عشان منوقفش الموقع - المزامنة هتتحاول تاني في الطلب الجاي
        pass


class AutoSyncMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        self._maybe_trigger_sync()
        return self.get_response(request)

    def _maybe_trigger_sync(self):
        now = time.time()
        with _lock:
            if now - _last_sync_time[0] < SYNC_COOLDOWN_SECONDS:
                return
            _last_sync_time[0] = now
        threading.Thread(target=_run_sync, daemon=True).start()
