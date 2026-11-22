from decimal import Decimal
from unittest.mock import patch
from urllib.parse import urlparse, parse_qs

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from .models import Address, Category, ContactMessage, Coupon, CouponRedemption, Order, OrderItem, Product, ProductReview, WishlistItem


@override_settings(SECURE_SSL_REDIRECT=False)
class CommerceApiTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("shopper", "shopper@example.com", "GoodPassword123!")
        self.category = Category.objects.create(name="Sofas", slug="sofas")
        self.product = Product.objects.create(
            name="Luna Sofa", slug="luna-sofa", category=self.category,
            description="A comfortable sofa", price=Decimal("1000.00"), stock=5,
        )
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def order_payload(self, **overrides):
        return {
            "full_name": "Test Shopper", "email": "shopper@example.com", "phone": "9876543210",
            "address": "10 Test Street", "city": "Mumbai", "postal_code": "400001",
            "items": [{"product_id": self.product.id, "quantity": 2}], **overrides,
        }

    def test_coupon_order_reduces_stock_and_records_tracking_and_redemption(self):
        coupon = Coupon.objects.create(code="SAVE10", discount_type="percent", discount_value=10)

        response = self.client.post("/api/orders/", self.order_payload(coupon_code="save10"), format="json")

        self.assertEqual(response.status_code, 201, response.data)
        order = Order.objects.get(pk=response.data["id"])
        self.product.refresh_from_db()
        self.assertEqual(order.total, Decimal("2799.00"))
        self.assertEqual(order.discount_amount, Decimal("200.00"))
        self.assertEqual(order.shipping_amount, Decimal("999.00"))
        self.assertEqual(order.tax_amount, Decimal("274.58"))
        self.assertEqual(self.product.stock, 3)
        self.assertEqual(order.tracking_code, response.data["tracking_code"])
        self.assertTrue(CouponRedemption.objects.filter(coupon=coupon, user=self.user, order=order).exists())

    def test_invalid_coupon_rolls_back_stock_deduction(self):
        response = self.client.post("/api/orders/", self.order_payload(coupon_code="NOPE"), format="json")

        self.assertEqual(response.status_code, 400)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 5)
        self.assertEqual(Order.objects.count(), 0)

    def test_guest_can_quote_home_coupon_only_on_eligible_products(self):
        home = Category.objects.create(name="Home Decor", slug="home-decor")
        lamps = Category.objects.create(name="Lamps", slug="lamps", parent=home)
        lamp = Product.objects.create(name="Lamp", slug="lamp", category=lamps, price=6000, stock=2)
        coupon = Coupon.objects.create(code="HOME600", discount_type="fixed", discount_value=600, minimum_order=5000)
        coupon.categories.add(home)
        guest = APIClient()

        response = guest.post("/api/coupons/validate/", {
            "code": coupon.code, "items": [{"product_id": lamp.id, "quantity": 1}],
        }, format="json")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["discount"], Decimal("600.00"))

        response = guest.post("/api/coupons/validate/", {
            "code": coupon.code, "items": [{"product_id": self.product.id, "quantity": 1}],
        }, format="json")
        self.assertEqual(response.status_code, 400, response.data)

    def test_order_and_callback_reject_bad_phone_and_pin(self):
        payload = self.order_payload(phone="12345678901", postal_code="40001")
        order = self.client.post("/api/orders/", payload, format="json")
        self.assertEqual(order.status_code, 400, order.data)
        self.assertIn("phone", order.data)
        self.assertIn("postal_code", order.data)

        callback = self.client.post("/api/callback-requests/", {
            "name": payload["full_name"], "email": payload["email"], "phone": payload["phone"],
            "postal_code": "400001", "message": "Please call me about a sofa.",
        }, format="json")
        self.assertEqual(callback.status_code, 400, callback.data)
        self.assertIn("10-digit", callback.data["detail"])

    @override_settings(DEBUG=True)
    def test_test_payment_is_simulated_as_paid_in_debug(self):
        response = self.client.post("/api/orders/", self.order_payload(payment_method="test_card"), format="json")

        self.assertEqual(response.status_code, 201, response.data)
        order = Order.objects.get(pk=response.data["id"])
        self.assertEqual(order.payment_method, "test_card")
        self.assertEqual(order.payment_status, "paid")

    def test_wishlist_and_addresses_are_scoped_to_authenticated_user(self):
        response = self.client.post("/api/wishlist/", {"product_id": self.product.id}, format="json")
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(WishlistItem.objects.filter(user=self.user).count(), 1)

        address = {
            "label": "Home", "full_name": "Test Shopper", "phone": "9876543210",
            "address": "10 Test Street", "city": "Mumbai", "postal_code": "400001", "is_default": True,
        }
        created = self.client.post("/api/addresses/", address, format="json")
        self.assertEqual(created.status_code, 201, created.data)
        self.assertEqual(Address.objects.get(user=self.user).city, "Mumbai")

        other_user = User.objects.create_user("other", password="GoodPassword123!")
        other_client = APIClient()
        other_client.force_authenticate(other_user)
        self.assertEqual(other_client.get("/api/wishlist/").data, [])
        self.assertEqual(other_client.get("/api/addresses/").data, [])

    def test_verified_buyer_review_is_saved_pending_approval(self):
        order = Order.objects.create(
            user=self.user, full_name="Test Shopper", email="shopper@example.com", phone="9876543210",
            address="10 Test Street", city="Mumbai", postal_code="400001", total=Decimal("1000.00"),
            status="delivered",
        )
        OrderItem.objects.create(order=order, product=self.product, product_name=self.product.name, quantity=1, unit_price=self.product.price)

        response = self.client.post("/api/reviews/", {
            "product": self.product.id, "rating": 5, "body": "Comfortable and well made.",
        }, format="json")

        self.assertEqual(response.status_code, 201, response.data)
        self.assertFalse(ProductReview.objects.get().is_approved)
        self.assertEqual(self.client.get(f"/api/reviews/?product={self.product.id}").data, [])

    @override_settings(DEBUG=True)
    def test_profile_updates_persist_and_password_reset_link_changes_password(self):
        profile_response = self.client.patch("/api/profile/", {
            "first_name": "Luna", "email": "new-shopper@example.com", "phone": "9876500000",
        }, format="json")
        self.assertEqual(profile_response.status_code, 200, profile_response.data)
        self.assertEqual(profile_response.data["phone"], "9876500000")
        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, "Luna")
        self.assertEqual(self.user.email, "new-shopper@example.com")

        reset = APIClient().post("/api/auth/password-reset/", {
            "email": "new-shopper@example.com",
        }, format="json")
        self.assertEqual(reset.status_code, 200)
        reset_query = parse_qs(urlparse(reset.data["development_reset_link"]).query)
        uid, token = reset_query["reset"][0].split(".", 1)
        confirmed = APIClient().post("/api/auth/password-reset/confirm/", {
            "uid": uid, "token": token, "new_password": "NewSecurePassword123!",
        }, format="json")
        self.assertEqual(confirmed.status_code, 200, confirmed.data)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("NewSecurePassword123!"))

    def test_admin_metrics_are_staff_only_and_report_live_catalog(self):
        denied = self.client.get("/api/admin/stats/")
        self.assertEqual(denied.status_code, 403)
        staff = User.objects.create_superuser("manager", "manager@example.com", "ManagerPassword123!")
        admin_client = APIClient()
        admin_client.force_authenticate(staff)
        result = admin_client.get("/api/admin/stats/")
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.data["products"], 1)
        self.assertEqual(result.data["users"], 1)

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_contact_enquiry_is_saved_and_notified_when_email_is_available(self):
        from django.core import mail

        response = APIClient().post("/api/contact/", {
            "name": "A Customer", "email": "customer@example.com", "phone": "9876543210",
            "message": "I need help choosing a sofa for my living room.",
        }, format="json")

        self.assertEqual(response.status_code, 201, response.data)
        enquiry = ContactMessage.objects.get()
        self.assertEqual(enquiry.name, "A Customer")
        self.assertTrue(enquiry.notification_sent)
        self.assertEqual(len(mail.outbox), 1)

    @patch("store.views.EmailMessage.send", side_effect=OSError("SMTP unavailable"))
    def test_contact_enquiry_is_kept_in_admin_inbox_when_email_is_unavailable(self, _send_mail):
        with self.assertLogs("store.views", level="ERROR"):
            response = APIClient().post("/api/contact/", {
                "name": "A Customer", "email": "customer@example.com",
                "message": "I need help choosing a sofa for my living room.",
            }, format="json")

        self.assertEqual(response.status_code, 201, response.data)
        enquiry = ContactMessage.objects.get()
        self.assertFalse(enquiry.notification_sent)
        self.assertIn("saved for our support team", response.data["detail"])

