from django.conf import settings
from django.contrib.auth.views import redirect_to_login


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
        "/favicon.ico",
        "/robots.txt",
    }

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if self._requires_login(request):
            return redirect_to_login(
                request.get_full_path(),
                login_url=getattr(settings, "LOGIN_URL", None),
            )
        return self.get_response(request)

    def _requires_login(self, request):
        if request.user.is_authenticated:
            return False

        # Let API/AJAX (JSON) requests fall through to the view so it can return a
        # proper 401 JSON response instead of a 302 redirect to an HTML login page.
        if self._expects_json(request):
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
