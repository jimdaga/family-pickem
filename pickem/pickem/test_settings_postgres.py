"""Test settings backed by PostgreSQL — the production database engine.

Used by the grading integration workflow so the suite runs against real
Postgres behavior (transactions, constraint timing, DISTINCT semantics)
instead of SQLite. Everything else is inherited from test_settings.

Connection comes from the same DATABASE_* variables production uses,
defaulting to a local service on 5432 (the GitHub Actions service
container). The test runner creates/migrates its own `test_<NAME>`
database, so the configured user needs CREATEDB.
"""

import os

from pickem.test_settings import *  # noqa: F401, F403

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.environ.get('DATABASE_NAME', 'pickem_test'),
        'USER': os.environ.get('DATABASE_USER', 'postgres'),
        'PASSWORD': os.environ.get('DATABASE_PASS', 'postgres'),
        'HOST': os.environ.get('DATABASE_HOST', 'localhost'),
        'PORT': os.environ.get('DATABASE_PORT', '5432'),
    }
}
