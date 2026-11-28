import io
import json
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from .models import CallbackRequest, NewsletterSubscriber, SiteBranding


class StorefrontSettingsTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()

    def test_only_staff_can_publish_valid_social_profiles(self):
        url = "/api/branding/"
        profile = "https://www.instagram.com/eroma_example/"
        self.assertEqual(self.client.patch(url, {"instagram": profile}, format="json").status_code, 401)
        staff = get_user_model().objects.create(username="staff", is_staff=True)
        self.client.force_authenticate(staff)
        spoofed_url = "https://instagram.com.example.org/eroma"
        self.assertEqual(self.client.patch(url, {"instagram": spoofed_url}, format="json").status_code, 400)
        saved = self.client.patch(url, {"instagram": profile, "assistant_mode": "off"}, format="json")
        self.assertEqual(saved.status_code, 200, saved.data)
        public = APIClient().get(url)
        self.assertEqual(public.data["instagram"], profile)
        self.assertEqual(public.data["assistant_mode"], "off")

    def test_newsletter_validates_addresses_and_deduplicates_retries(self):
        url = "/api/newsletter/"
        self.assertEqual(self.client.post(url, {"email": "invalid"}, format="json").status_code, 400)
        for email in ("Furniture@Example.org", "furniture@example.org"):
            self.assertEqual(self.client.post(url, {"email": email}, format="json").status_code, 200)
        self.assertEqual(list(NewsletterSubscriber.objects.values_list("email", flat=True)), ["furniture@example.org"])

    @override_settings(GEMINI_API_KEY="example")
    @patch("store.views.urllib.request.urlopen")
    def test_chat_modes_and_provider_filters(self, provider):
        url = "/api/assistant/chat/"
        payload = {"messages": [{"role": "user", "text": "What sofas do you sell?"}]}
        settings = SiteBranding.objects.create(assistant_mode="guide")
        guide = self.client.post(url, payload, format="json")
        self.assertEqual(guide.data["source"], "store-help")
        provider.assert_not_called()
        settings.assistant_mode = "off"
        settings.save(update_fields=["assistant_mode"])
        self.assertEqual(self.client.post(url, payload, format="json").status_code, 503)
        settings.assistant_mode = "gemini"
        settings.save(update_fields=["assistant_mode"])
        for message in ("Explain calculus", "Order status for shopper@example.org"):
            response = self.client.post(url, {"messages": [{"role": "user", "text": message}]}, format="json")
            self.assertEqual(response.data["source"], "store-help")
        provider.assert_not_called()

        provider.return_value.__enter__.return_value = io.BytesIO(json.dumps({
            "candidates": [{"finishReason": "SAFETY", "content": {"parts": [{"text": "Blocked text"}]}}],
        }).encode())
        response = self.client.post(url, payload, format="json")
        self.assertEqual(response.data["source"], "store-help")
        self.assertNotIn("Blocked text", response.data["answer"])
        sent = json.loads(provider.call_args.args[0].data)
        self.assertEqual(len(sent["safetySettings"]), 4)
        self.assertTrue(all(setting["threshold"] == "BLOCK_LOW_AND_ABOVE" for setting in sent["safetySettings"]))

    @override_settings(
        RESEND_API_KEY="example",
        SUPPORT_NOTIFICATION_EMAIL="support@example.org",
    )
    @patch("store.email_backend.requests.post")
    def test_callback_uses_transactional_provider_and_preserves_reply_address(self, provider):
        provider.return_value.status_code = 200
        response = self.client.post("/api/callback-requests/", {
            "name": "Shopper", "email": "shopper@example.org", "phone": "9876543210",
            "postal_code": "560001", "message": "Please help with delivery.",
        }, format="json")
        self.assertEqual(response.status_code, 201, response.data)
        self.assertTrue(CallbackRequest.objects.get().notification_sent)
        sent = provider.call_args.kwargs["json"]
        self.assertEqual(sent["to"], ["support@example.org"])
        self.assertEqual(sent["reply_to"], ["shopper@example.org"])
