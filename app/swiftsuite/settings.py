
from pathlib import Path
from datetime import timedelta
from decouple import config
import cloudinary
from email.utils import formataddr

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/5.0/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = config('SECRET_KEY')

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = config('DEBUG', cast=bool)

ALLOWED_HOSTS = [
    "service-test.vps.swiftsuite.app",
    "service.swiftsuite.app",
    "127.0.0.1"
]

# Application definition

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "accounts",
    "marketplaceApp",
    "inventoryApp",
    "orderApp",
    "vendorActivities",
    "vendorEnrollment",
    "notificationApp",
    "reportApp",
    "rest_framework",
    "corsheaders",
    'cloudinary',
    'cloudinary_storage',
    'rest_framework_extensions',
    'drf_spectacular',
    'rest_framework_simplejwt.token_blacklist',
    'django_cleanup.apps.CleanupConfig'
]

CORS_ALLOWED_ORIGINS = [
    "https://swiftsuite.app",
    "https://frontend-test.vps.swiftsuite.app",
    "http://localhost:5173",
    "http://127.0.0.1"
]

# CORS_ALLOW_ALL_ORIGINS = True

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "swiftsuite.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR, 'templates/'],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "swiftsuite.wsgi.application"

AUTH_USER_MODEL = 'accounts.User'

REST_FRAMEWORK = {
    
    'DEFAULT_AUTHENTICATION_CLASSES': (
    
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ),
    "DEFAULT_PERMISSION_CLASSES": (
        "rest_framework.permissions.AllowAny",  
    ),
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
}

REST_FRAMEWORK_EXTENSIONS = {
    'DEFAULT_CACHE_RESPONSE_TIMEOUT': 60*5,  # Cache timeout in seconds
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(hours=12),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=1),

    "AUTH_HEADER_TYPES": ("Bearer",),
}

SPECTACULAR_SETTINGS = {
    'TITLE': 'SwiftSuite Service API',
    'DESCRIPTION': 'API documentation for SwiftSuite Service',
    'VERSION': '1.0.0',
    'SERVE_INCLUDE_SCHEMA': False,
    'COMPONENT_SPLIT_REQUEST': True,
}

# Database
# https://docs.djangoproject.com/en/5.0/ref/settings/#databases

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': config('DB_NAME'),
        'USER': config('DB_USER'),
        'PASSWORD': config('DB_PASSWORD'),
        "HOST": config("DB_HOST", default="127.0.0.1"),
        "PORT": config("DB_PORT", cast=int, default=3306),
        'OPTIONS': {
            'autocommit': True,
        },
    }
}


DEFAULT_FROM_EMAIL = config("DEFAULT_FROM_EMAIL")

# Password validation
# https://docs.djangoproject.com/en/5.0/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]


# Internationalization
# https://docs.djangoproject.com/en/5.0/topics/i18n/

LANGUAGE_CODE = "en-us"

TIME_ZONE = "UTC"

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/5.0/howto/static-files/

STATIC_URL = "/static/"

# Default primary key field type
# https://docs.djangoproject.com/en/5.0/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

STRIPE_SECRET_KEY = config("STRIPE_SECRET_KEY")
STRIPE_WEBHOOK_SECRET = config("STRIPE_WEBHOOK_SECRET")
STRIPE_VENDOR_WEBHOOK_SECRET = config("STRIPE_VENDOR_WEBHOOK_SECRET")

DEFAULT_FILE_STORAGE = 'cloudinary_storage.storage.MediaCloudinaryStorage'

# Cloudinary Configuration       
cloudinary.config(
    CLOUD_NAME = config("cloud_name"),
    API_KEY = config("api_key"),
    API_SECRET = config("api_secret"),
    secure = config("secure")
)

CLOUDINARY_STORAGE = {
    "CLOUD_NAME": config("cloud_name"),
    "API_KEY": config("api_key"),
    "API_SECRET": config("api_secret"),
}

# Configuration for celery
CELERY_BROKER_URL = config("CELERY_BROKER_URL")
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_BACKEND = config("CELERY_RESULT_BACKEND")
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = "UTC"

CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": config("REDIS_CACHE_LOCATION"),
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
        }
    }
}

O365_CLIENT_ID = config("O365_CLIENT_ID")
O365_CLIENT_SECRET = config("O365_CLIENT_SECRET")
O365_TENANT_ID = config("O365_TENANT_ID", default=None)