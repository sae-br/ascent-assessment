from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from apps.assessments.models import Assessment

class PromoCode(models.Model):
    code = models.CharField(max_length=64, unique=True, help_text="Case-insensitive; will be uppercased on save.")
 
    # exactly one of the two must be set
    percent_off = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True,
                                      help_text="0–100.00")
    amount_off = models.IntegerField(null=True, blank=True,
                                     help_text="Fixed discount in MINOR units (e.g., cents).")

    currency = models.CharField(max_length=10, blank=True,
                                help_text="Required if using amount_off. Example: 'cad'.")

    active = models.BooleanField(default=True)
    starts_at = models.DateTimeField(null=True, blank=True)
    ends_at = models.DateTimeField(null=True, blank=True)

    max_redemptions = models.PositiveIntegerField(null=True, blank=True,
                                                  help_text="Global cap across all users. Leave blank for unlimited.")
    per_user_limit = models.PositiveIntegerField(default=1, help_text="How many times a single user can redeem.")
    min_subtotal = models.IntegerField(null=True, blank=True,
                                       help_text="Minimum subtotal (minor units) required to apply.")
    first_purchase_only = models.BooleanField(default=False)

    notes = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.code

    def clean(self):
        # normalize
        if self.code:
            self.code = self.code.strip().upper()

        # validate exclusive discount fields
        has_percent = self.percent_off is not None
        has_amount = self.amount_off is not None
        if has_percent == has_amount:
            raise ValidationError("Provide either percent_off or amount_off (exclusively).")

        if has_percent:
            if not (0 < float(self.percent_off) <= 100.0):
                raise ValidationError("percent_off must be between 0 and 100.")
        if has_amount and not self.currency:
            raise ValidationError("currency is required when amount_off is used.")

        # time window sanity
        if self.starts_at and self.ends_at and self.starts_at >= self.ends_at:
            raise ValidationError("starts_at must be before ends_at.")

    # State checks
    def is_active_now(self, now=None):
        if not self.active:
            return False
        now = now or timezone.now()
        if self.starts_at and now < self.starts_at:
            return False
        if self.ends_at and now >= self.ends_at:
            return False
        return True

    # Discount calculation (returns (discount_minor, final_minor))
    def compute_discount(self, subtotal_minor, currency, stripe_min_charge_minor=50):
        """
        Ensure result respects Stripe min charge. Clamp if discount would go below minimum.
        """
        if self.amount_off is not None:
            if self.currency.lower() != currency.lower():
                # incompatible currency; no discount
                return 0, subtotal_minor
            discount = min(self.amount_off, subtotal_minor)
        else:
            pct = float(self.percent_off) / 100.0
            discount = int(round(subtotal_minor * pct))

        final_amount = max(subtotal_minor - discount, stripe_min_charge_minor)
        # If clamped, reduce the discount accordingly
        if final_amount == stripe_min_charge_minor:
            discount = subtotal_minor - final_amount
        return discount, final_amount


class Redemption(models.Model):
    promocode = models.ForeignKey(PromoCode, on_delete=models.PROTECT, related_name="redemptions")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="promocode_redemptions")
    assessment = models.ForeignKey(Assessment, on_delete=models.CASCADE, related_name="promocode_redemptions")

    payment_intent_id = models.CharField(max_length=64)
    amount_before = models.IntegerField(help_text="Minor units")
    discount_applied = models.IntegerField(help_text="Minor units")
    amount_after = models.IntegerField(help_text="Minor units")

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["payment_intent_id"]),
            models.Index(fields=["user", "promocode"]),
        ]
        # Prevent accidental duplicate redemption logs for the same order by the same user if something retries
        unique_together = [("promocode", "user", "assessment")]

    def __str__(self):
        return f"{self.promocode.code} → {self.user} ({self.amount_after})"