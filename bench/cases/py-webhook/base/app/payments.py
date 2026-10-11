"""Payment provider integration."""

import hashlib
import hmac
import os

from app.store import orders

WEBHOOK_SECRET = os.environ["PAYMENT_WEBHOOK_SECRET"].encode()


def sign(body: bytes) -> str:
    """Hex HMAC-SHA256 of a webhook body, as the provider computes it."""
    return hmac.new(WEBHOOK_SECRET, body, hashlib.sha256).hexdigest()


def mark_paid(order_id: str) -> None:
    orders[order_id]["status"] = "paid"
