import os
import local__config as local



"""
Django settings for trd_app project.

Generated by 'django-admin startproject' using Django 4.1.10.

For more information on this file, see
https://docs.djangoproject.com/en/4.1/topics/settings/

For the full list of settings and their values, see
https://docs.djangoproject.com/en/4.1/ref/settings/
"""

from pathlib import Path

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/4.1/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = local.DJANGO_SK

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = local.DEBUG

ALLOWED_HOSTS = local.DJANGO_ALLOWED_HOSTS

SECURE_CROSS_ORIGIN_OPENER_POLICY =  None


# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.humanize',
    'django_extensions',
    'django_pandas',
    'user',
    'bot',
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

ROOT_URLCONF = 'trd_app.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'django.template.context_processors.i18n',
                'django.contrib.auth.context_processors.auth',
                'bot.context_processors.local_values',
            ],
        },
    },
]

WSGI_APPLICATION = 'trd_app.wsgi.application'


# Database
# https://docs.djangoproject.com/en/4.1/ref/settings/#databases

if not local.LOC_DB_TYPE:
    local.LOC_DB_TYPE = 'default'

if local.LOC_DB_TYPE == 'default':
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db_sqlite/trd_app.sqlite3',
        }
    }
elif local.LOC_DB_TYPE == 'mysql':
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.mysql',
            'NAME': local.LOC_MYSQL_DB,
            'USER': local.LOC_MYSQL_U,
            'PASSWORD': local.LOC_MYSQL_P,
            'HOST': local.LOC_MYSQL_H,   # Or an IP Address that your DB is hosted on
            'PORT': '3306',
        }
    }
elif local.LOC_DB_TYPE == 'postgresql':
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': local.LOC_MYSQL_DB,
            'USER': local.LOC_MYSQL_U,
            'PASSWORD': local.LOC_MYSQL_P,
            'HOST': local.LOC_MYSQL_H,
            'PORT': 5432,
        }
    }


# Password validation
# https://docs.djangoproject.com/en/4.1/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


# Internationalization
# https://docs.djangoproject.com/en/4.1/topics/i18n/

LANGUAGE_CODE = 'es'

TIME_ZONE = 'America/Argentina/Buenos_Aires'
#TIME_ZONE = 'UTC'
USE_TZ = False

DATE_FORMAT = 'd-m-Y'
DATE_INPUT_FORMATS = 'd-m-Y'

DATETIME_FORMAT = 'd-m-Y H:i'
DATETIME_INPUT_FORMATS = 'd-m-Y H:i'

USE_L10N = False



# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/4.1/howto/static-files/

STATIC_URL = '/static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')
STATICFILES_DIRS = (os.path.join(BASE_DIR,'static'),)

CSRF_TRUSTED_ORIGINS = ['http://*','https://*',]


# Default primary key field type
# https://docs.djangoproject.com/en/4.1/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'


LOGIN_URL = 'signin'


EMAIL_HOST = 'smtp.gmail.com'
EMAIL_HOST_USER = 'leonardo.bisaro@gmail.com'
EMAIL_HOST_PASSWORD = 'Fmn361612'
EMAIL_PORT = 587
EMAIL_USE_TLS = True
DEFAULT_FROM_EMAIL = 'leonardo.bisaro@gmail.com'


