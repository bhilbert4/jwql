"""Django settings for ``jwql`` project.

Contains essential project settings, including a list of installed
apps, where to find templates, credentials for connection to the
``db.sqlite3`` database, time zone, & locations where static files are
located. Generated by ``django-admin startproject`` using Django 2.0.1.

Authors
-------

    - Lauren Chambers

References
----------

    For more information on this file, see
        ``https://docs.djangoproject.com/en/2.0/topics/settings/``
    For the full list of settings and their values, see
        ``https://docs.djangoproject.com/en/2.0/ref/settings/``

Dependencies
------------

    The user must have a configuration file named ``config.json``
    placed in the ``jwql/utils/`` directory.
"""

import os

from jwql.utils.utils import get_config
from django.contrib.messages import constants as messages

# Build paths inside the project like this: os.path.join(BASE_DIR, ...)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# SECURITY WARNING: keep the secret key used in production secret!
if not os.environ.get("READTHEDOCS"):
    SECRET_KEY = get_config()['django_secret_key']

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True


ALLOWED_HOSTS = ['*']

# Application definition
INSTALLED_APPS = [
    'jwql.website.apps.jwql',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
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

ROOT_URLCONF = 'jwql.website.jwql_proj.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.jinja2.Jinja2',
        'DIRS': [os.path.join(BASE_DIR, 'apps', 'jwql', 'templates')],
        'APP_DIRS': True,
        'OPTIONS': {
            'environment': 'jwql.website.jwql_proj.jinja2.environment',
            'extensions': ['jwql.website.jwql_proj.jinja2.DjangoNow'],
            'context_processors': [
                'jwql.website.apps.jwql.context_processors.base_context',
                'django.contrib.messages.context_processors.messages'
            ],
        },
    },
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'django.template.context_processors.request'
            ],
        },
    },
]

MESSAGE_TAGS = {
        messages.DEBUG: 'alert-secondary',
        messages.INFO: 'alert-info',
        messages.SUCCESS: 'alert-success',
        messages.WARNING: 'alert-warning',
        messages.ERROR: 'alert-danger',
 }

WSGI_APPLICATION = 'jwql.website.jwql_proj.wsgi.application'


# Database
# https://docs.djangoproject.com/en/2.0/ref/settings/#databases
DATABASES = {
    'default': get_config()['django_database']
}

# Password validation
# https://docs.djangoproject.com/en/2.0/ref/settings/#auth-password-validators

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
# https://docs.djangoproject.com/en/2.0/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'EST'

USE_I18N = True

USE_L10N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/2.0/howto/static-files/

STATIC_URL = '/static/'

STATICFILES_DIRS = [
    os.path.join(BASE_DIR, "apps", "jwql", "static/"),
    get_config()['jwql_dir']
]

# Use integer for auto primary key, as was default before django 3.2
DEFAULT_AUTO_FIELD = 'django.db.models.AutoField'

# Add trusted origins for CSRF origin checking
CSRF_TRUSTED_ORIGINS = ['https://jwql.stsci.edu',
                        'https://jwql-test.stsci.edu',
                        'https://jwql-dev.stsci.edu',
                        'https://127.0.0.1']
