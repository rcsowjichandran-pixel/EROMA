import csv
from decimal import Decimal
from io import BytesIO
from unittest.mock import patch
from urllib.parse import urlparse, parse_qs

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings
from PIL import Image
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

    def test_registration_applies_django_password_validators(self):
        guest = APIClient()
        payload = {"username": "newshopper", "email": "new@example.test", "password": "password123"}
        weak = guest.post("/api/auth/register/", payload, format="json")
        self.assertEqual(weak.status_code, 400, weak.data)
        self.assertIn("password", weak.data)
        self.assertFalse(User.objects.filter(username=payload["username"]).exists())
        payload["password"] = "Maple!Gallery529"
        strong = guest.post("/api/auth/register/", payload, format="json")
        self.assertEqual(strong.status_code, 201, strong.data)
        self.assertTrue(User.objects.get(username=payload["username"]).check_password(payload["password"]))

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

    def test_cents_and_coupon_quote_match_the_cod_order(self):
        self.product.price = Decimal("1000.01")
        self.product.save(update_fields=["price"])
        Coupon.objects.create(code="SAVE5", discount_type="percent", discount_value=Decimal("5.00"))
        payload = self.order_payload(coupon_code="SAVE5", items=[{"product_id": self.product.id, "quantity": 1}])
        quote = self.client.post("/api/coupons/validate/", {"code": "SAVE5", "items": payload["items"]}, format="json")
        placed = self.client.post("/api/orders/", payload, format="json")
        self.assertEqual(placed.status_code, 201, placed.data)
        self.assertEqual(Decimal(placed.data["discount_amount"]), quote.data["discount"])
        self.assertEqual(Decimal(placed.data["tax_amount"]), Decimal("144.92"))
        self.assertEqual(Decimal(placed.data["total"]), Decimal("1949.01"))
        self.assertEqual(self.client.get(f"/api/products/{self.product.id}/").data["stock"], 4)

    def test_bill_download_is_limited_to_the_order_owner_and_eligible_orders(self):
        placed = self.client.post("/api/orders/", self.order_payload(), format="json")
        self.assertEqual(placed.status_code, 201, placed.data)
        self.assertTrue(placed.data["bill_available"])
        order_id = placed.data["id"]
        url = f"/api/orders/{order_id}/bill/"

        bill = self.client.get(url)
        self.assertEqual(bill.status_code, 200)
        self.assertEqual(bill["Content-Type"], "application/pdf")
        self.assertEqual(bill["Content-Disposition"], f'attachment; filename="EROMA-bill-{order_id}.pdf"')
        pdf = b"".join(bill.streaming_content)
        self.assertTrue(pdf.startswith(b"%PDF-"))
        self.assertIn(b"/Subtype /Image", pdf)

        other = APIClient()
        other.force_authenticate(User.objects.create_user("other-shopper"))
        self.assertEqual(other.get(url).status_code, 404)
        self.assertEqual(APIClient().get(url).status_code, 401)

        orders = Order.objects.filter(pk=order_id)
        orders.update(payment_method="razorpay", payment_status="pending")
        self.assertEqual(self.client.get(url).status_code, 409)
        orders.update(payment_status="paid")
        paid = self.client.get(url)
        self.assertEqual(paid.status_code, 200)
        paid.close()
        orders.update(status="cancelled")
        self.assertEqual(self.client.get(url).status_code, 409)

    @override_settings(RAZORPAY_KEY_ID="test-id", RAZORPAY_KEY_SECRET="test-secret")
    @patch("store.views._razorpay_request")
    def test_failed_razorpay_releases_stock_once_and_excludes_attempt_from_order_counts(self, gateway):
        Coupon.objects.create(code="SAVE10", discount_type="percent", discount_value=10)
        gateway.side_effect = [
            {"id": "order_failed", "amount": 279900, "currency": "INR"},
            {"items": [{"status": "failed"}]},
        ]
        started = self.client.post("/api/payments/razorpay/create-order/", self.order_payload(coupon_code="SAVE10"), format="json")
        self.assertEqual(started.status_code, 200, started.data)
        self.assertEqual(started.data["prefill"]["contact"], "+919876543210")
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 3)
        order_id = started.data["order_id"]
        self.user.is_staff = True
        self.user.save(update_fields=["is_staff"])
        self.assertEqual(self.client.get("/api/admin/stats/").data["pending_orders"], 0)

        for _ in range(2):
            cancelled = self.client.post("/api/payments/razorpay/cancel/", {"order_id": order_id}, format="json")
            self.assertEqual(cancelled.data, {"cancelled": True})
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 5)
        order = Order.objects.get(pk=order_id)
        self.assertEqual((order.payment_status, order.status), ("failed", "cancelled"))
        self.assertFalse(CouponRedemption.objects.filter(order=order).exists())
        self.assertEqual(self.client.get("/api/admin/stats/").data["orders"], 0)
        self.assertEqual(gateway.call_count, 2)

    @override_settings(RAZORPAY_KEY_ID="test-id", RAZORPAY_KEY_SECRET="test-secret")
    @patch("store.views._razorpay_request")
    def test_cancel_reconciles_a_payment_already_captured(self, gateway):
        payment = {"id": "pay_captured", "order_id": "order_captured", "amount": 299900,
                   "currency": "INR", "method": "card", "status": "captured"}
        gateway.side_effect = [
            {"id": "order_captured", "amount": 299900, "currency": "INR"},
            {"items": [{**payment, "status": "authorized"}]},
            {"items": [payment]},
        ]
        started = self.client.post("/api/payments/razorpay/create-order/", self.order_payload(), format="json")
        self.assertEqual(started.status_code, 200, started.data)
        payload = {"order_id": started.data["order_id"]}
        pending = self.client.post("/api/payments/razorpay/cancel/", payload, format="json")
        self.assertEqual(pending.status_code, 409, pending.data)
        captured = self.client.post("/api/payments/razorpay/cancel/", payload, format="json")
        self.assertEqual(captured.data["order"]["payment_status"], "paid")
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 3)

    @override_settings(RAZORPAY_KEY_ID="test-id", RAZORPAY_KEY_SECRET="test-secret")
    @patch("store.views._razorpay_request")
    def test_emi_checkout_refunds_a_captured_non_emi_charge_and_releases_stock_once(self, gateway):
        payment = {"id": "pay_card", "order_id": "order_emi", "amount": 299900,
                   "currency": "INR", "method": "card", "status": "captured"}
        gateway.side_effect = [
            {"id": "order_emi", "amount": 299900, "currency": "INR"},
            {"items": [payment]},
            {"id": "refund_card", "payment_id": "pay_card", "amount": 299900, "status": "processed"},
        ]
        started = self.client.post("/api/payments/razorpay/create-order/", self.order_payload(emi_requested=True), format="json")
        self.assertEqual(started.status_code, 200, started.data)
        order_id = started.data["order_id"]
        for _ in range(2):
            result = self.client.post("/api/payments/razorpay/cancel/", {"order_id": order_id}, format="json")
            self.assertEqual(result.data, {"cancelled": True, "refunded": True})
        gateway.assert_called_with("POST", "payments/pay_card/refund", {"amount": 299900},
                                   idempotency_key="eroma-emi-mismatch-pay_card")
        self.assertEqual(gateway.call_count, 3)
        order = Order.objects.get(pk=order_id)
        self.assertEqual((order.payment_status, order.status, order.razorpay_payment_id),
                         ("refunded", "cancelled", "pay_card"))
        self.assertFalse(order.bill_available)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 5)

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

    def test_dinning_search_matches_dining_furniture(self):
        dining = Category.objects.create(name="Dining Furniture", slug="dining")
        tables = Category.objects.create(name="Dining Tables", slug="dining-tables", parent=dining)
        table = Product.objects.create(name="Oak table", slug="oak-table", category=tables, price=6000, stock=2)
        response = APIClient().get("/api/products/", {"search": "dinning"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual([item["id"] for item in response.data], [table.id])

    @override_settings(STORAGES={
        "default": {"BACKEND": "django.core.files.storage.InMemoryStorage"},
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    })
    def test_staff_can_add_alternate_photos_without_replacing_the_product_cover(self):
        self.product.image_url = "https://example.com/luna-main.jpg"
        self.product.save(update_fields=["image_url"])
        url = f"/api/products/{self.product.id}/gallery/"
        self.assertEqual(self.client.post(url, {}, format="multipart").status_code, 403)
        self.user.is_staff = True
        self.user.save(update_fields=["is_staff"])
        picture = BytesIO()
        Image.new("RGB", (4, 4), "white").save(picture, format="PNG")
        response = self.client.post(url, {
            "images": [SimpleUploadedFile(name, picture.getvalue(), "image/png") for name in ("side.png", "rear.png")],
        }, format="multipart")
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data["image_url"], self.product.image_url)
        self.assertEqual([photo["sort_order"] for photo in response.data["images"]], [1, 2])
        self.assertFalse(any(photo["is_primary"] for photo in response.data["images"]))

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

    @override_settings(
        DEBUG=False, RESEND_API_KEY="test-key", DEFAULT_FROM_EMAIL="EROMA <reset@example.com>",
        FRONTEND_URL="https://eroma-1.onrender.com",
    )
    @patch("store.email_backend.requests.post")
    def test_hosted_password_reset_sends_a_usable_link_over_https(self, send):
        send.return_value.status_code = 200
        guest = APIClient()
        reset = guest.post("/api/auth/password-reset/", {"email": self.user.email}, format="json")
        self.assertEqual(reset.status_code, 200, reset.data)
        self.assertNotIn("development_reset_link", reset.data)
        send.assert_called_once()
        self.assertEqual(send.call_args.args, ("https://api.resend.com/emails",))
        self.assertEqual(send.call_args.kwargs["headers"], {"Authorization": "Bearer test-key"})
        payload = send.call_args.kwargs["json"]
        self.assertEqual(payload["from"], "EROMA <reset@example.com>")
        self.assertEqual(payload["to"], [self.user.email])
        link = urlparse(payload["text"].split()[-1])
        self.assertEqual((link.scheme, link.hostname), ("https", "eroma-1.onrender.com"))
        uid, token = parse_qs(link.query)["reset"][0].split(".", 1)
        confirmed = guest.post("/api/auth/password-reset/confirm/", {
            "uid": uid, "token": token, "new_password": "NewSecurePassword123!",
        }, format="json")
        self.assertEqual(confirmed.status_code, 200, confirmed.data)

        send.return_value.status_code = 403
        with self.assertLogs("store.views", level="ERROR"):
            rejected = guest.post("/api/auth/password-reset/", {"email": self.user.email}, format="json")
        self.assertEqual(rejected.status_code, 503)
        self.assertNotIn("development_reset_link", rejected.data)

    def test_sales_csv_is_staff_only_and_exports_confirmed_orders_without_customer_details(self):
        placed = self.client.post("/api/orders/", self.order_payload(), format="json")
        self.assertEqual(placed.status_code, 201, placed.data)
        cancelled = self.client.post("/api/orders/", self.order_payload(), format="json")
        self.assertEqual(cancelled.status_code, 201, cancelled.data)
        Order.objects.filter(pk=cancelled.data["id"]).update(status="cancelled")

        url = "/api/admin/sales-report/"
        self.assertEqual(self.client.get(url).status_code, 403)
        self.user.is_staff = True
        self.user.save(update_fields=["is_staff"])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Disposition"], 'attachment; filename="EROMA-sales-report.csv"')
        report = response.content.decode("utf-8")
        rows = list(csv.DictReader(report.splitlines()))
        self.assertEqual([row["Order ID"] for row in rows], [str(placed.data["id"])])
        self.assertEqual(rows[0]["Total (INR)"], placed.data["total"])
        self.assertNotIn(self.user.email, report)
        self.assertNotIn(placed.data["address"], report)

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

    def test_admin_order_list_displays_and_searches_tracking_code(self):
        placed = self.client.post("/api/orders/", self.order_payload(), format="json")
        self.assertEqual(placed.status_code, 201, placed.data)
        tracking_code = placed.data["tracking_code"]
        self.user.is_staff = True
        self.user.is_superuser = True
        self.user.save(update_fields=["is_staff", "is_superuser"])
        admin_client = Client()
        admin_client.force_login(self.user)

        order_list = admin_client.get("/admin/store/order/")
        self.assertContains(order_list, "Tracking code")
        self.assertContains(order_list, tracking_code)
        search = admin_client.get("/admin/store/order/", {"q": tracking_code})
        self.assertContains(search, tracking_code)

    def test_admin_dashboard_separates_confirmed_and_paid_order_counts(self):
        cod = self.client.post("/api/orders/", self.order_payload(quantity=1), format="json")
        paid = self.client.post("/api/orders/", self.order_payload(quantity=1), format="json")
        self.assertEqual((cod.status_code, paid.status_code), (201, 201))
        Order.objects.filter(pk=paid.data["id"]).update(payment_method="razorpay", payment_status="paid")
        self.user.is_staff = True
        self.user.is_superuser = True
        self.user.save(update_fields=["is_staff", "is_superuser"])
        admin_client = Client()
        admin_client.force_login(self.user)

        dashboard = admin_client.get("/admin/")
        self.assertEqual(dashboard.context["fulfillment_total"], 2)
        self.assertEqual(dashboard.context["paid_orders"], 1)
        self.assertContains(dashboard, 'href="/admin/store/order/?payment_status__exact=paid">1 paid order</a>')

    @override_settings(GEMINI_API_KEY="")
    def test_store_assistant_compares_wooden_and_cushioned_sofas_without_ai(self):
        response = APIClient().post("/api/assistant/chat/", {
            "messages": [{"role": "user", "text": "Which will you suggest, wooden or cushion sofa?"}],
        }, format="json")

        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["source"], "store-help")
        self.assertEqual(response["X-EROMA-Assistant-Status"], "gemini-key-missing")
        self.assertIn("everyday comfort", response.data["answer"])
        self.assertIn("choose cushioned", response.data["answer"])
        self.assertNotIn("Here are a few available options", response.data["answer"])

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

