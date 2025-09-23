from django.conf import settings
import stripe, logging
logger = logging.getLogger(__name__)


def _normalize_addr(billing_address: dict) -> dict:
    """Return a dict with only the fields Stripe expects, uppercasing country/state where present."""
    addr = billing_address or {}
    country = (addr.get("country") or "").upper() or None
    state = (addr.get("state") or "").upper() or None
    norm = {
        "country": country,
        "postal_code": addr.get("postal_code") or None,
        "state": state,
        "city": addr.get("city") or None,
        "line1": addr.get("line1") or None,
        # Optional line2 omitted
    }
    # Drop empty keys
    return {k: v for k, v in norm.items() if v}


def _create_tax_calculation(*, currency: str, amount_minor: int, tax_code: str, customer_address: dict):
    """
    Call Stripe Tax Calculations using whichever namespace exists in the installed SDK.
    Newer SDKs: stripe.tax.calculations.create
    Older SDKs: stripe.Tax.Calculations.create
    """
    payload = {
        "currency": currency,
        "customer_details": {
            "address": customer_address,
            # Hint to Stripe that this is the billing address
            "address_source": "billing",
            # Respect any tax-exempt logic you add later; for now explicit none
            "tax_exempt": "none",
        },
        "line_items": [{
            "amount": int(amount_minor),
            "reference": "final_report",
            "tax_code": tax_code,
        }],
    }

    # Try the new namespace first
    try:
        return stripe.tax.calculations.create(**payload)  # type: ignore[attr-defined]
    except AttributeError:
        # Fall back to the older class namespace
        return stripe.Tax.Calculations.create(**payload)  # type: ignore[attr-defined]


def compute_tax_minor(amount_after_discount_minor, currency, billing_address):
    """
    Return the tax amount (in minor units) for the single line item.
    - If no country, fallback to 0 (can’t determine jurisdiction).
    - Supports both new and old Stripe SDKs for Tax Calculations.
    - Requires a valid settings.STRIPE_TAX_CODE_FINAL_REPORT.
    """
    try:
        amt = int(amount_after_discount_minor or 0)
    except (TypeError, ValueError):
        amt = 0

    if amt <= 0:
        return 0

    # Validate address
    addr = _normalize_addr(billing_address or {})
    if not addr.get("country"):
        return 0  # no jurisdiction

    tax_code = getattr(settings, "STRIPE_TAX_CODE_FINAL_REPORT", None)
    if not tax_code or tax_code == "txcd_99999999":
        logger.warning("Stripe Tax: using placeholder/undefined tax code; returning 0 tax.")
        return 0

    try:
        calc = _create_tax_calculation(
            currency=currency,
            amount_minor=amt,
            tax_code=tax_code,
            customer_address=addr,
        )
        # calc.amount_total includes subtotal + tax; guard types
        amount_total = int(getattr(calc, "amount_total", 0) or 0)
        tax_amount = max(amount_total - amt, 0)
        return tax_amount
    except Exception as e:
        logger.warning("Stripe Tax calculation failed: %s", e)
        return 0