"""
ASGI config for pickem project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/3.0/howto/deployment/asgi/
"""

import os

from django.conf import settings
from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'pickem.settings')

application = get_asgi_application()

# Unlike `runserver`, a bare ASGI server (uvicorn) does not serve static files,
# so a local uvicorn run (e.g. scripts/live-sim.sh) renders every page unstyled.
# In DEBUG, wrap the app so it serves collected/static-finder assets itself —
# the same handler `runserver` uses under ASGI. In production DEBUG is off and
# static is served from S3, so this wrapping never applies there.
if settings.DEBUG:
    from django.contrib.staticfiles.handlers import ASGIStaticFilesHandler

    application = ASGIStaticFilesHandler(application)
