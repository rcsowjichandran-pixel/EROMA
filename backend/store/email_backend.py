import requests
from django.conf import settings
from django.core.mail import get_connection
from django.core.mail.backends.base import BaseEmailBackend


def transactional_connection():
    if settings.RESEND_API_KEY:
        return get_connection("store.email_backend.ResendEmailBackend")
    return None


class ResendEmailBackend(BaseEmailBackend):
    def send_messages(self, email_messages):
        sent = 0
        for message in email_messages or ():
            if not message.recipients():
                continue
            payload = {
                "from": message.from_email,
                "to": message.to,
                "subject": message.subject,
                "text": message.body,
            }
            if message.reply_to:
                payload["reply_to"] = message.reply_to
            try:
                if not settings.RESEND_API_KEY:
                    raise RuntimeError("Resend API key is missing.")
                response = requests.post(
                    "https://api.resend.com/emails",
                    json=payload,
                    headers={"Authorization": f"Bearer {settings.RESEND_API_KEY}"},
                    timeout=settings.EMAIL_TIMEOUT,
                    allow_redirects=False,
                )
                if not 200 <= response.status_code < 300:
                    raise RuntimeError(f"Resend rejected the email (HTTP {response.status_code}).")
            except (requests.RequestException, RuntimeError):
                if not self.fail_silently:
                    raise
            else:
                sent += 1
        return sent
