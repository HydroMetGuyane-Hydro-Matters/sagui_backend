"""
Django settings for sagui_backend project.

Generated by 'django-admin startproject' using Django 3.2.13.

For more information on this file, see
https://docs.djangoproject.com/en/3.2/topics/settings/

For the full list of settings and their values, see
https://docs.djangoproject.com/en/3.2/ref/settings/
"""

import environ
from pathlib import Path
import os

env = environ.FileAwareEnv(
    # set casting, default value
    DEBUG=(bool, False)
)

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# reading .env file
env.read_env()

# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/3.2/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
# SECRET_KEY = 'django-insecure-+u!f)2atyd6dra_%^9wlm!80h2x&^jti8!x)7!j22j#@--m_p6'
SECRET_KEY = env('SECRET_KEY')

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = env('DEBUG')

# ALLOWED_HOSTS = []
ALLOWED_HOSTS = env('ALLOWED_HOSTS').split(',')
print('allowed hosts:{}'.format(ALLOWED_HOSTS))


# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.gis',
    'rest_framework',
    'drf_spectacular',
    'colorfield',
    'sagui',
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

ROOT_URLCONF = 'sagui_backend.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [os.path.join(BASE_DIR, "templates")],
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

WSGI_APPLICATION = 'sagui_backend.wsgi.application'


# Database
# https://docs.djangoproject.com/en/3.2/ref/settings/#databases

DATABASES = {
    # 'default': {
    #     'ENGINE': 'django.db.backends.sqlite3',
    #     'NAME': BASE_DIR / 'db.sqlite3',
    # }
    'default': {
        'ENGINE': 'django.contrib.gis.db.backends.postgis',
        'OPTIONS': {
            'options': '-c search_path=guyane,hyfaa,geospatial,public,topology'
        },
        'HOST'  : env('POSTGRES_HOST'),
        'PORT'  : env('POSTGRES_PORT'),
        'NAME'  : env('POSTGRES_DB'),
        'USER'  : env('POSTGRES_USER'),
        'PASSWORD': env('POSTGRES_PASSWORD'),
    }
}


# Password validation
# https://docs.djangoproject.com/en/3.2/ref/settings/#auth-password-validators

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
# https://docs.djangoproject.com/en/3.2/topics/i18n/

LANGUAGE_CODE = 'fr-fr'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_L10N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/3.2/howto/static-files/

STATIC_URL = env('STATIC_URL')
STATIC_ROOT = env('STATIC_ROOT')
MEDIA_ROOT = env('MEDIA_ROOT')
MEDIA_URL = env('MEDIA_URL')

# Default primary key field type
# https://docs.djangoproject.com/en/3.2/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

REST_FRAMEWORK = {
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 50,
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
}
SPECTACULAR_SETTINGS = {
    'TITLE': 'SAGUI API',
    'DESCRIPTION': 'Sig d’Alerte pour la Guyane sur l’eaU et l’aIr',
    'VERSION': '1.0.0',
    'SERVE_INCLUDE_SCHEMA': False,
    # OTHER SETTINGS
    'SCHEMA_PATH_PREFIX': r'/api/v[0-9]',
    'SORT_OPERATION_PARAMETERS': False,
}

SAGUI_SETTINGS = {
    'RECORD_DECIMALS': 2,
    'SAGUI_COORDINATES_ROUND_DECIMALS': 5,
    'SAGUI_PATH_TO_ATMO_FILES': env('SAGUI_PATH_TO_ATMO_FILES', default='/home/jean/dev/HM/sagui_platform/atmo_s5p/data/styled/'),
    'DRAINAGE_VT_URL': env('DRAINAGE_VT_URL', default=''),
    'RAINFALL_NETCDF_FILES_PATH': env('RAINFALL_NETCDF_FILES_PATH', default=None),
    'HYFAA_IMPORT_NETCDF_ROOT_PATH': env('HYFAA_IMPORT_NETCDF_ROOT_PATH', default=None),
    'HYFAA_DATABASE_URI': env('HYFAA_DATABASE_URI', default=None),
    'HYFAA_DATABASE_SCHEMA': env('HYFAA_DATABASE_SCHEMA', default='guyane'),
    'HYFAA_IMPORT_COMMIT_PAGE_SIZE': env('HYFAA_IMPORT_COMMIT_PAGE_SIZE', default=1),
    'HYFAA_IMPORT_STRUCTURE_CONFIG': {
     # Configures where to find the netcdf data and what to retrieve (var names)
     # Also configures the names mapping between the netcdf data and the database
     # (simplifies the naming of the variables, that was very verbose)
        'sources': [
            {
                'name': 'mgbstandard',
                'file': 'mgbstandard_solution_databases/post_processing_portal.nc',
                'nc_data_vars': [
                    'water_elevation_catchment_mean',
                    'streamflow_catchment_mean',
                 ],
                'tablename': 'hyfaa_data_mgbstandard'
            },
            {
                'name': 'forecast',
                'file': 'mgbstandard_solution_databases/prevision_using_previous_years/post_processing_portal.nc',
                'nc_data_vars': [
                    'water_elevation_catchment_mean',
                    'water_elevation_catchment_median',
                    'water_elevation_catchment_std',
                    'water_elevation_catchment_mad',
                    'streamflow_catchment_mean',
                    'streamflow_catchment_median',
                    'streamflow_catchment_std',
                    'streamflow_catchment_mad',
                 ],
                'tablename': 'hyfaa_data_forecast'
            },
            {
                'name': 'assimilated',
                'file': 'assimilated_solution_databases/post_processing_portal.nc',
                'nc_data_vars': [
                    'water_elevation_catchment_mean',
                    'water_elevation_catchment_median',
                    'water_elevation_catchment_std',
                    'water_elevation_catchment_mad',
                    'streamflow_catchment_mean',
                    'streamflow_catchment_median',
                    'streamflow_catchment_std',
                    'streamflow_catchment_mad',
                 ],
                'tablename': 'hyfaa_data_assimilated'
            },
          ],
          'short_names': {
            'water_elevation_catchment_mean': 'elevation_mean',
            'water_elevation_catchment_median': 'elevation_median',
            'water_elevation_catchment_std': 'elevation_stddev',
            'water_elevation_catchment_mad': 'elevation_mad',
            'streamflow_catchment_mean': 'flow_mean',
            'streamflow_catchment_median': 'flow_median',
            'streamflow_catchment_std': 'flow_stddev',
            'streamflow_catchment_mad': 'flow_mad',
          }
    }
}