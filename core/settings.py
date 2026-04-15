import os
import dj_database_url
import cloudinary
import cloudinary.uploader
import cloudinary.api
from pathlib import Path

# --- 1. BASE PATHS ---
BASE_DIR = Path(__file__).resolve().parent.parent

# --- 2. SECURITY ---
SECRET_KEY = os.environ.get('SECRET_KEY', 'django-insecure-wwu+#v0r1jyidt2h(9(^^*b9l3io-wtltox-p&%o=8ho2bq37q')
DEBUG = os.environ.get('DEBUG', 'True') == 'True'
ALLOWED_HOSTS = ['.render.com', 'localhost', '127.0.0.1']

# --- 3. APPLICATION DEFINITION ---
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'cloudinary_storage',         # Keep above staticfiles
    'django.contrib.staticfiles',
    'cloudinary',
    'rest_framework',
    'drf_spectacular',
    'accounts',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'core.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'core.wsgi.application'

# --- 4. DATABASE (Neon Cloud) ---
DATABASES = {
    'default': dj_database_url.config(
        default='postgresql://neondb_owner:npg_Ici6aXEq2Nyf@ep-proud-hall-ano1xx9z.c-6.us-east-1.aws.neon.tech/neondb?sslmode=require',
        conn_max_age=600,
        conn_health_checks=True,
    )
}

# --- 5. AUTHENTICATION ---
AUTH_USER_MODEL = 'accounts.BankUser'
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# --- 6. INTERNATIONALIZATION ---
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

# --- 7. STATIC FILES (WhiteNoise) ---
STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# --- 8. MEDIA FILES (Cloudinary) ---
CLOUDINARY_STORAGE = {
    'CLOUD_NAME': 'dhwihfv09',
    'API_KEY': '137271666832499',
    'API_SECRET': 'lb3ykYQQcygr1BOw74XJq0PMGEQ' # Replace with real secret
}

# Force handshake to prevent "Must supply api_key" error
cloudinary.config(
    cloud_name = CLOUDINARY_STORAGE['CLOUD_NAME'],
    api_key = CLOUDINARY_STORAGE['API_KEY'],
    api_secret = CLOUDINARY_STORAGE['API_SECRET'],
    secure = True
)

DEFAULT_FILE_STORAGE = 'cloudinary_storage.storage.MediaCloudinaryStorage'
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# --- 9. BIOMETRIC API (Face++) ---
# This fixes the 'Settings' object has no attribute 'FACE_API_SECRET' error
FACE_API_KEY = 'xQWWO1L1PQGUZ98FNey7qbXvTSi99nXa'
FACE_API_SECRET = 'A1fct0LOQrb0oqm7od7aDfHBfxPTRwPk'
FACE_API_ENDPOINT = "https://api-cn.faceplusplus.com/facepp/v3/compare"

# --- 10. API DOCUMENTATION ---
REST_FRAMEWORK = {
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
}

SPECTACULAR_SETTINGS = {
    'TITLE': 'Trust-Us-Banking API',
    'DESCRIPTION': 'Banking transactions system with facial biometric security',
    'VERSION': '1.0.0',
}

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'