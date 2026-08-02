"""
Test settings for the pickem project.

Overrides production settings with test-friendly defaults:
- SQLite in-memory database (fast, no external deps)
- Stable SECRET_KEY (not from environment)
- Rate limiting disabled
- S3 storage disabled (use local filesystem)
"""

import os
os.environ.setdefault('SECRET_KEY', 'test-secret-key-do-not-use-in-production')

from pickem.settings import *  # noqa: F401, F403

# Use SQLite in-memory for fast tests
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': ':memory:',
    }
}

# Stable secret key for tests (not from environment)
SECRET_KEY = 'test-secret-key-do-not-use-in-production'

# Ensure debug is on for better test error output
DEBUG = True

# Disable rate limiting
RATELIMIT_ENABLE = False

# Use default local storage (no S3). Django 5.x uses the STORAGES dict;
# the legacy STATICFILES_STORAGE/DEFAULT_FILE_STORAGE settings were removed.
STORAGES = {
    'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
    'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
}

# Silence password hashing for faster tests
PASSWORD_HASHERS = [
    'django.contrib.auth.hashers.MD5PasswordHasher',
]

# Disable logging noise during tests
LOGGING = {}

# Ensure django.contrib.sites is available (needed by allauth and Site model in tests)
if 'django.contrib.sites' not in INSTALLED_APPS:
    INSTALLED_APPS = list(INSTALLED_APPS) + ['django.contrib.sites']
