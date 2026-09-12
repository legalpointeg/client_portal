"""
client_portal/client_portal/settings.py
-----------------------------------------
إعدادات Django الأساسية لمشروع بوابة العميل المستقلة.
"""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# ============================================================
# أمان أساسي - عدّل دول قبل أي نشر فعلي (production)
# ============================================================
SECRET_KEY = os.environ.get(
    'DJANGO_SECRET_KEY',
    'CHANGE-ME-dev-only-secret-key-not-for-production',
)
DEBUG = os.environ.get('DJANGO_DEBUG', 'False') == 'True'
ALLOWED_HOSTS = os.environ.get('DJANGO_ALLOWED_HOSTS', '*').split(',')

# ============================================================
# التطبيقات
# ============================================================
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    'clients',  # التطبيق الأساسي لبوابة العميل
    'uploads',  # مشروع الزميل المدموج - مزامنة
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'client_portal.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'client_portal.wsgi.application'

# ============================================================
# قاعدة البيانات
# ============================================================
# SQLite مبدئيًا لتقليل استهلاك المساحة والتبعيات وقت التجربة.
# للانتقال لـ MySQL لاحقًا: استبدل الإعداد ده بنفس نمط lawfirm_portal
# (يحتاج وقتها تثبيت mysqlclient بعد حل موضوع الـ disk quota).
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    },
    'uploads_db': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': '/home/legalpointeg/upload_receiver/db.sqlite3',
    },
}

DATABASE_ROUTERS = ['uploads.db_router.UploadsRouter']

# ============================================================
# نموذج المستخدم المخصص - إلزامي يكون هنا قبل أول migration
# ============================================================
AUTH_USER_MODEL = 'clients.Client'

# ============================================================
# التحقق من كلمة المرور
# ============================================================
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# ============================================================
# اللغة والمنطقة الزمنية
# ============================================================
LANGUAGE_CODE = 'ar'
TIME_ZONE = 'Africa/Cairo'
USE_I18N = True
USE_TZ = True

# ============================================================
# الملفات الثابتة
# ============================================================
STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [BASE_DIR / 'static']

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ============================================================
# إعدادات Google Drive (نفس حساب lawfirm_portal الأصلي)
# ============================================================
# عدّل القيمة دي لنفس DRIVE_ROOT_FOLDER_ID الموجود في lawfirm_portal/settings.py
# للتأكد: grep -n "DRIVE_ROOT_FOLDER_ID" ~/lawfirm_portal/*/settings.py (أو ملف .env هناك)
DRIVE_ROOT_FOLDER_ID = '1DzKOHcqMS_Wg44GRhhsTnTCrbGXdk1kd'

# ============================================================
# إعدادات تسجيل الدخول
# ============================================================
LOGIN_URL = '/login/'
LOGIN_REDIRECT_URL = '/dashboard/'
LOGOUT_REDIRECT_URL = '/login/'

# ============================================================
# إعدادات المزامنة مع lawfirm_portal
# ============================================================
LAWFIRM_API_BASE_URL = 'https://Lexpoint.pythonanywhere.com'
PORTAL_SYNC_API_KEY = 'UGkkeXPHA2ol0NoUO1s7c27L9wlef3myDmID67W2SJ8'
