import os
from pathlib import Path
from decouple import config

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = 'hHJpT19rp09eC8q2B10-sxpN00H_DDjAyyzhJAfJYM0jYwuoWICRAZyHAz'
DEBUG = False
ALLOWED_HOSTS = config("ALLOWED_HOSTS", default="*").split(",")

INSTALLED_APPS = [
    'apps.crm',
    'apps.platform_core',
    'apps.tasks',
    'apps.payments',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.humanize',
    # Third party
    'rest_framework',
    'crispy_forms',
    'crispy_bootstrap5',
    'django_celery_beat',
    'django_celery_results',
    # Local apps
    'apps.accounts',
    'apps.campaigns',
    'apps.recipients',
    'apps.templates_mgr',
    'apps.reports',
    'apps.accounting',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'apps.platform_core.permission_middleware.TenantPermissionMiddleware',
    'apps.platform_core.tenant_context.TenantContextMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

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
                'apps.platform_core.context_processors.tenant_permissions',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': config('DB_NAME', default='inexc_email'),
        'USER': config('DB_USER', default='postgres'),
        'PASSWORD': config('DB_PASSWORD', default='postgres'),
        'HOST': config('DB_HOST', default='localhost'),
        'PORT': config('DB_PORT', default='5432'),
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'ar'
TIME_ZONE = 'Asia/Dubai'
USE_I18N = True
USE_TZ = True

STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

LOGIN_URL = '/accounts/login/'
LOGIN_REDIRECT_URL = '/'
LOGOUT_REDIRECT_URL = '/accounts/login/'

CRISPY_ALLOWED_TEMPLATE_PACKS = 'bootstrap5'
CRISPY_TEMPLATE_PACK = 'bootstrap5'

# ─── Celery ───────────────────────────────────────────────
CELERY_BROKER_URL = config('CELERY_BROKER_URL', default='redis://localhost:6379/0')
CELERY_RESULT_BACKEND = config('CELERY_RESULT_BACKEND', default='redis://localhost:6379/0')
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = TIME_ZONE
CELERY_BEAT_SCHEDULER = 'django_celery_beat.schedulers:DatabaseScheduler'
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_TIME_LIMIT = 30 * 60

# ─── EmailJS ──────────────────────────────────────────────
EMAILJS_SERVICE_ID  = config('EMAILJS_SERVICE_ID', default='')
EMAILJS_TEMPLATE_ID = config('EMAILJS_TEMPLATE_ID', default='')
EMAILJS_PUBLIC_KEY  = config('EMAILJS_PUBLIC_KEY',  default='')
EMAILJS_PRIVATE_KEY = config('EMAILJS_PRIVATE_KEY', default='')

# ─── Sending Config ───────────────────────────────────────
BATCH_SIZE           = config('BATCH_SIZE',           default=50,  cast=int)
BATCH_DELAY_SECONDS  = config('BATCH_DELAY_SECONDS',  default=2,   cast=int)
MAX_RETRIES          = config('MAX_RETRIES',          default=3,   cast=int)
DAILY_SEND_LIMIT = config('DAILY_SEND_LIMIT', default=2000, cast=int)
FAILURE_THRESHOLD = config('FAILURE_THRESHOLD', default=20, cast=int)
RETRY_DELAY_SECONDS  = config('RETRY_DELAY_SECONDS',  default=60,  cast=int)

# ─── Session ──────────────────────────────────────────────
SESSION_COOKIE_AGE = 86400
SESSION_EXPIRE_AT_BROWSER_CLOSE = False

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.SessionAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
}

# ===== Stripe Payment Settings =====
STRIPE_SECRET_KEY = config('STRIPE_SECRET_KEY', default='')
STRIPE_PUBLISHABLE_KEY = config('STRIPE_PUBLISHABLE_KEY', default='')
STRIPE_CURRENCY = config('STRIPE_CURRENCY', default='aed')

STRIPE_WEBHOOK_SECRET = config('STRIPE_WEBHOOK_SECRET', default='')


# EmailJS server-side settings
EMAILJS_SERVICE_ID = config('EMAILJS_SERVICE_ID', default='')
EMAILJS_TEMPLATE_ID = config('EMAILJS_TEMPLATE_ID', default='')
EMAILJS_PUBLIC_KEY = config('EMAILJS_PUBLIC_KEY', default='')
EMAILJS_PRIVATE_KEY = config('EMAILJS_PRIVATE_KEY', default='')


# Gmail SMTP
EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = config("EMAIL_HOST", default="smtp.gmail.com")
EMAIL_PORT = config("EMAIL_PORT", default=587, cast=int)
EMAIL_USE_TLS = config("EMAIL_USE_TLS", default=True, cast=bool)
EMAIL_HOST_USER = config("EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = config("EMAIL_HOST_PASSWORD", default="")
DEFAULT_FROM_EMAIL = config("DEFAULT_FROM_EMAIL", default="INEXC <info@inexc.com>")
