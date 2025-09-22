from django.db.models import Count
from django.utils import timezone
from apps.payments.models import PromoCode, Redemption

class PromoInvalid(Exception):
    pass

def normalize_code(code: str) -> str:
    return (code or "").strip().upper()

def validate_and_price(code_str, user, assessment, subtotal_minor, currency, require_first_purchase=False):
    """
    Returns dict:
      {
        "promocode": <PromoCode or None>,
        "discount_minor": int,
        "final_minor": int,
        "reason": "ok" | "...error key..."
      }
    Raises PromoInvalid for invalid cases (caller can show message).
    """
    code = normalize_code(code_str)
    if not code:
        raise PromoInvalid("Enter a code.")

    try:
        pc = PromoCode.objects.get(code=code)
    except PromoCode.DoesNotExist:
        raise PromoInvalid("That code isn’t valid.")

    if not pc.is_active_now(timezone.now()):
        raise PromoInvalid("That code isn’t active right now.")

    if pc.min_subtotal and subtotal_minor < pc.min_subtotal:
        raise PromoInvalid("Order total is too low for this code.")

    # global cap
    if pc.max_redemptions is not None and pc.redemptions.count() >= pc.max_redemptions:
        raise PromoInvalid("This code has reached its limit.")

    # per-user cap
    user_count = pc.redemptions.filter(user=user).count()
    if user_count >= pc.per_user_limit:
        raise PromoInvalid("You’ve already used this code.")

    # optional: first-purchase-only
    if pc.first_purchase_only or require_first_purchase:
        # Consider "first purchase" as no successful redemptions by this user at all.
        if Redemption.objects.filter(user=user).exists():
            raise PromoInvalid("This code is for first-time purchases only.")

    discount, final_amount = pc.compute_discount(subtotal_minor, currency)
    return {
        "promocode": pc,
        "discount_minor": discount,
        "final_minor": final_amount,
        "reason": "ok",
    }