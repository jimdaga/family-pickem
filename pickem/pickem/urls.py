"""pickem URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/3.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.conf import settings
from django.conf.urls.static import static
from django.db import Error as DBError
from django.http import JsonResponse
from django.urls import include, path
from django.views.decorators.http import require_GET
from pickem_api.models import currentSeason


@require_GET
def healthz(request):
    """Liveness/readiness probe target: DB connectivity, nothing else.

    Deliberately does not render the homepage (probes hitting `/` were
    running the full context-processor/query stack every ~10s for no
    diagnostic benefit). `.exists()` forces a real round-trip through the
    ORM rather than a hand-written query, and `django.db.Error` (rather
    than just OperationalError) also catches a stale/closed persistent
    connection (InterfaceError) surfacing as a probe failure.
    """
    try:
        currentSeason.objects.exists()
    except DBError:
        return JsonResponse({'status': 'error', 'database': 'unreachable'}, status=503)
    return JsonResponse({'status': 'ok'})


urlpatterns = [
    path('healthz/', healthz, name='healthz'),
    path('', include('pickem_homepage.urls')),
    path('admin/', admin.site.urls),
    path('superadmin/', include('pickem_superadmin.urls')),
]

# Development-only delivery for the locally processed logo fallback. Production
# logo objects remain private S3 keys and are served through their signed URLs.
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
