import re
from django.core.validators import RegexValidator


PHONE_PATTERN = re.compile(r"\A[0-9]{10}\Z")
PIN_PATTERN = re.compile(r"\A[0-9]{6}\Z")
PHONE_ERROR = "Enter a 10-digit phone number."
PIN_ERROR = "Enter a 6-digit PIN code."
validate_phone = RegexValidator(PHONE_PATTERN, PHONE_ERROR)
validate_pin = RegexValidator(PIN_PATTERN, PIN_ERROR)
