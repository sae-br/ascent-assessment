# Minimal CSP middleware for the whole site.
# - Keeps things simple (no per-request nonces).
# - Allows posting/redirecting to Stripe Checkout only via form-action.
# - Blocks framing, limits scripts to self, permits inline styles (many sites rely on this).

from django.utils.deprecation import MiddlewareMixin

_SIMPLE_CSP = (
    "default-src 'self'; "
    "script-src 'self' https://unpkg.com; "
    "style-src 'self' 'unsafe-inline'; "
    "img-src 'self' data:; "
    "font-src 'self'; "
    "connect-src 'self'; "
    "frame-src 'none'; "
    "base-uri 'self'; "
    "form-action 'self' https://checkout.stripe.com"
)

class CSPMiddleware(MiddlewareMixin):
    def process_response(self, request, response):
        response['Content-Security-Policy'] = _SIMPLE_CSP
        return response