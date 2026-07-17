"""Extra security headers on every backend response."""

RELAXED_CSP_PREFIXES = ("/admin/", "/api/v1/docs/")  # need their own scripts/styles

STRICT_CSP = "default-src 'none'; frame-ancestors 'none'; base-uri 'none'"
RELAXED_CSP = (
    "default-src 'self'; script-src 'self' 'unsafe-inline'; "
    "style-src 'self' 'unsafe-inline'; img-src 'self' data:; "
    "font-src 'self'; frame-ancestors 'none'; base-uri 'self'"
)


class SecurityHeadersMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        path = request.path
        if "Content-Security-Policy" not in response:
            if path.startswith(RELAXED_CSP_PREFIXES):
                response["Content-Security-Policy"] = RELAXED_CSP
            else:
                response["Content-Security-Policy"] = STRICT_CSP
        response.setdefault("X-Content-Type-Options", "nosniff")
        response.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        response.setdefault("Cross-Origin-Opener-Policy", "same-origin")
        return response
