import io
import json
from unittest.mock import patch

from django.core.cache import cache
from django.test import TestCase, override_settings
from rest_framework.test import APIClient


@override_settings(GEMINI_API_KEY="test-key")
class ChatRestrictionTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()

    def ask(self, text):
        return self.client.post("/api/assistant/chat/", {
            "messages": [{"role": "user", "text": text}],
        }, format="json")

    @patch("store.views.urllib.request.urlopen")
    def test_unrelated_questions_and_personal_details_stay_local(self, provider):
        self.assertEqual(self.ask("Explain calculus")["X-EROMA-Assistant-Status"], "restricted-topic")
        self.assertEqual(
            self.ask("Order status for shopper@example.org")["X-EROMA-Assistant-Status"],
            "restricted-personal-information",
        )
        provider.assert_not_called()

    @patch("store.views.urllib.request.urlopen")
    def test_valid_chat_uses_filters_and_discards_blocked_output(self, provider):
        for finish_reason, source in (("STOP", "gemini"), ("SAFETY", "store-help")):
            provider.return_value.__enter__.return_value = io.BytesIO(json.dumps({
                "candidates": [{"finishReason": finish_reason, "content": {"parts": [{"text": "Example reply"}]}}],
            }).encode())
            response = self.ask("Compare leather and fabric sofas.")
            self.assertEqual(response.data["source"], source)
            if finish_reason == "SAFETY":
                self.assertNotIn("Example reply", response.data["answer"])
            payload = json.loads(provider.call_args.args[0].data)
            self.assertEqual(len(payload["safetySettings"]), 4)
            self.assertTrue(all(
                item["threshold"] == "BLOCK_LOW_AND_ABOVE" for item in payload["safetySettings"]
            ))
