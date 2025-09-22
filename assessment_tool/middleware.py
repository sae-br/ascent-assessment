from django.conf import settings
import secrets

# Two-tier CSP:
# - STRICT_CSP_TEMPLATE: used on /payments/* pages (Stripe Elements & SCA) with per-request nonces
# - RELAXED_CSP: used elsewhere to avoid breaking legacy inline scripts and keep DX simple
STRICT_CSP_TEMPLATE = (
    "default-src 'self'; "
    # Strict: require a per-request nonce for inline scripts on payment pages
    "script-src 'self' https://js.stripe.com https://s.stripe.com https://unpkg.com https://cdn.jsdelivr.net https://hcaptcha.com https://*.hcaptcha.com 'nonce-{nonce}'; "
    # Frames (Stripe Elements/3DS and hCaptcha when invoked)
    "frame-src https://js.stripe.com https://hooks.stripe.com https://hcaptcha.com https://*.hcaptcha.com; "
    # XHR/fetch (Stripe + telemetry); same-origin covered by 'self'
    "connect-src 'self' https://api.stripe.com https://m.stripe.network; "
    # Images (site + Stripe beacons); data: for inline SVG/PNG data URIs
    "img-src 'self' data: https://q.stripe.com https://s.stripe.com; "
    # Styles (keep inline allowed for now due to library defaults)
    "style-src 'self' 'unsafe-inline'; "
    # Fonts (local or embedded)
    "font-src 'self' data:; "
)

RELAXED_CSP = (
    "default-src 'self'; "
    # Relaxed: allow inline scripts to keep existing pages working without nonces
    "script-src 'self' https://js.stripe.com https://s.stripe.com https://unpkg.com https://cdn.jsdelivr.net https://hcaptcha.com https://*.hcaptcha.com 'unsafe-inline'; "
    "frame-src https://js.stripe.com https://hooks.stripe.com https://hcaptcha.com https://*.hcaptcha.com; "
    "connect-src 'self' https://api.stripe.com https://m.stripe.network; "
    "img-src 'self' data: https://q.stripe.com https://s.stripe.com; "
    "style-src 'self' 'unsafe-inline'; "
    "font-src 'self' data:; "
)


class CSPMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        
    def __call__(self, request):
        # Generate a per-request nonce and expose it to templates via `request.csp_nonce`
        request.csp_nonce = secrets.token_urlsafe(16)

        response = self.get_response(request)

        # Build the CSP. Allow override via settings.CSP_HEADER (for experiments).
        if hasattr(settings, "CSP_HEADER") and settings.CSP_HEADER:
            csp_value = settings.CSP_HEADER
        else:
            if request.path.startswith('/payments/'):
                csp_value = STRICT_CSP_TEMPLATE.format(nonce=request.csp_nonce)
            else:
                csp_value = RELAXED_CSP

        response["Content-Security-Policy"] = csp_value
        return response