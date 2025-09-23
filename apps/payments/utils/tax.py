from django.conf import settings
import stripe, logging, requests
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

_DEF_LINE_REF = "final_report"

def _build_tax_payload_form(currency: str, amount_minor: int, tax_code: str, customer_address: dict):
    data = {
        "currency": currency,
        "customer_details[address_source]": "billing",
        "customer_details[tax_exempt]": "none",
        "line_items[0][amount]": str(int(amount_minor)),
        "line_items[0][reference]": _DEF_LINE_REF,
        "line_items[0][tax_code]": tax_code,
    }
    # include only present address fields
    for k in ("country", "postal_code", "state", "city", "line1"):
        v = customer_address.get(k)
        if v:
            data[f"customer_details[address][{k}]"] = v
    return data


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
            "address_source": "billing",
            "tax_exempt": "none",
        },
        "line_items": [{
            "amount": int(amount_minor),
            "reference": _DEF_LINE_REF,
            "tax_code": tax_code,
        }],
    }

    # Try the new namespace first
    try:
        return stripe.tax.calculations.create(**payload)  # type: ignore[attr-defined]
    except AttributeError:
        pass
    except Exception as e:
        logger.debug("Stripe Tax (new) failed: %s", e)

    # Fall back to the older class namespace
    try:
        return stripe.Tax.Calculations.create(**payload)  # type: ignore[attr-defined]
    except AttributeError:
        pass
    except Exception as e:
        logger.debug("Stripe Tax (old) failed: %s", e)

    # Final fallback: direct REST call (SDK-agnostic)
    api_key = getattr(settings, "STRIPE_SECRET_KEY", None) or stripe.api_key
    if not api_key:
        raise RuntimeError("Missing STRIPE_SECRET_KEY for Stripe Tax REST call")
    form_data = _build_tax_payload_form(currency, amount_minor, tax_code, customer_address)
    resp = requests.post(
        "https://api.stripe.com/v1/tax/calculations",
        data=form_data,
        headers={"Authorization": f"Bearer {api_key}"},
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()


def compute_tax_minor(amount_after_discount_minor, currency, billing_address):
    """
    Return the tax amount (in minor units) for the single line item.
    - If no country, fallback to 0 (can’t determine jurisdiction).
    - Supports both new and old Stripe SDKs for Tax Calculations.
    """
    try:
        amt = int(amount_after_discount_minor or 0)
    except (TypeError, ValueError):
        amt = 0

    # Stripe expects 3-letter lowercase currency codes (e.g., 'cad')
    currency = (currency or "").lower() or "cad"

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

    logger.debug("Stripe Tax input: amt=%s currency=%s addr=%s", amt, currency, addr)

    try:
        calc = _create_tax_calculation(
            currency=currency,
            amount_minor=amt,
            tax_code=tax_code,
            customer_address=addr,
        )
        # calc may be a Stripe object or a dict (REST fallback)
        if isinstance(calc, dict):
            amount_total = int(calc.get("amount_total", 0) or 0)
        else:
            amount_total = int(getattr(calc, "amount_total", 0) or 0)
        tax_amount = max(amount_total - amt, 0)
        return tax_amount
    except Exception as e:
        logger.warning("Stripe Tax calculation failed: %s", e)
        return 0