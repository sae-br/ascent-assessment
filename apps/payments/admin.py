from django.contrib import admin
from django.utils.html import format_html
from .models import PromoCode, Redemption

@admin.register(PromoCode)
class PromoCodeAdmin(admin.ModelAdmin):
    list_display = (
        "code", "active", "percent_off", "amount_off", "currency",
        "window", "global_used", "max_redemptions", "per_user_limit",
    )
    list_filter = ("active", "first_purchase_only")
    search_fields = ("code", "notes")
    readonly_fields = ("created_at", "updated_at", "global_used_display")

    def window(self, obj):
        if obj.starts_at or obj.ends_at:
            return f"{obj.starts_at or '—'} → {obj.ends_at or '—'}"
        return "—"

    def global_used(self, obj):
        return obj.redemptions.count()

    def global_used_display(self, obj):
        return self.global_used(obj)

@admin.register(Redemption)
class RedemptionAdmin(admin.ModelAdmin):
    list_display = ("promocode", "user", "assessment", "amount_before",
                    "discount_applied", "amount_after", "payment_intent_id", "created_at")
    list_filter = ("promocode", "user")
    search_fields = ("payment_intent_id", "promocode__code", "user__email")
    readonly_fields = ("created_at",)