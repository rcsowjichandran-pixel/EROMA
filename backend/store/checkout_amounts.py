from decimal import Decimal, ROUND_HALF_UP

from django.conf import settings


def round_money(amount):
    return amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def coupon_discount(coupon, eligible_subtotal):
    amount = coupon.discount_value
    if coupon.discount_type == "percent":
        amount = eligible_subtotal * amount / 100
    return min(round_money(amount), eligible_subtotal)


def checkout_amounts(subtotal, discount):
    merchandise = subtotal - discount
    rate = settings.ORDER_GST_RATE
    gst = round_money(merchandise * rate / (100 + rate)) if rate > 0 else Decimal("0.00")
    delivery = Decimal("0.00") if merchandise >= settings.ORDER_FREE_DELIVERY_THRESHOLD else round_money(settings.ORDER_STANDARD_DELIVERY_FEE)
    return gst, delivery, merchandise + delivery
