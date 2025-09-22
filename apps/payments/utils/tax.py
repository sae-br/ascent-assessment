from django.conf import settings
import stripe, logging
logger = logging.getLogger(__name__)

def compute_tax_minor(amount_after_discount_minor, currency, billing_address):
    tax_code = getattr(settings, "STRIPE_TAX_CODE_FINAL_REPORT", None) or "txcd_99999999"
    country = (billing_address or {}).get("country")
    postal_code = (billing_address or {}).get("postal_code")
    if not country:
        return 0
    try:
        calc = stripe.tax.calculations.create(
            currency=currency,
            customer_details={"address": {
                "country": country,
                "postal_code": postal_code,
                "state": (billing_address or {}).get("state"),
                "city": (billing_address or {}).get("city"),
                "line1": (billing_address or {}).get("line1"),
            }},
            line_items=[{
                "amount": int(amount_after_discount_minor),
                "reference": "final_report",
                "tax_code": tax_code,
            }],
        )
        return max(int(calc.amount_total - amount_after_discount_minor), 0)
    except Exception as e:
        logger.warning("Stripe Tax calculation failed: %s", e)
        return 0