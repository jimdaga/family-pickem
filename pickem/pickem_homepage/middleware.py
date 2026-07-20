from django.conf import settings
from django.contrib.auth.views import redirect_to_login
from django.http import JsonResponse
from django.urls import resolve

from .upload_handlers import FamilyLogoUploadSizeLimitHandler


class FamilyLogoUploadHandlerMiddleware:
    """Install the logo stream limiter before CSRF parses multipart input."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        return self.get_response(request)

    def process_view(self, request, view_func, view_args, view_kwargs):
        content_type = request.META.get("CONTENT_TYPE", "")
        if request.method != "POST" or not content_type.startswith("multipart/form-data"):
            return None
        # `view_func` can be decorator-wrapped; the resolver's url_name is
        # stable and avoids installing a handler on similarly shaped routes.
        match = resolve(request.path_info)
        if match.url_name != "family_pool_admin_settings":
            return None
        request.upload_handlers.insert(0, FamilyLogoUploadSizeLimitHandler(request))
        return None


class RequireLoginForInternalPagesMiddleware:
    """Require authentication for web app routes except the public landing/login flow."""

    PUBLIC_PREFIXES = (
        "/accounts/",
        "/static/",
        "/media/",
        "/api/",
        "/admin/",
    )
    PUBLIC_EXACT_PATHS = {
        "/",
        "/public/",
        "/leaderboard/",
        "/favicon.ico",
        "/robots.txt",
    }

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if self._requires_login(request):
            # AJAX/JSON callers get a proper 401 instead of a 302 to an HTML
            # login page — but never a pass-through to the view: protected
            # pages must stay unreachable regardless of Accept headers.
            if self._expects_json(request):
                return JsonResponse(
                    {"error": "authentication required"}, status=401
                )
            return redirect_to_login(
                request.get_full_path(),
                login_url=getattr(settings, "LOGIN_URL", None),
            )
        return self.get_response(request)

    def _requires_login(self, request):
        if request.user.is_authenticated:
            return False

        path = request.path_info or "/"
        public_exact_paths = getattr(
            settings,
            "LOGIN_REQUIRED_PUBLIC_EXACT_PATHS",
            self.PUBLIC_EXACT_PATHS,
        )
        public_prefixes = getattr(
            settings,
            "LOGIN_REQUIRED_PUBLIC_PREFIXES",
            self.PUBLIC_PREFIXES,
        )

        if path in public_exact_paths:
            return False
        return not path.startswith(tuple(public_prefixes))

    @staticmethod
    def _expects_json(request):
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return True
        accept = request.headers.get("Accept", "")
        return "application/json" in accept and "text/html" not in accept
