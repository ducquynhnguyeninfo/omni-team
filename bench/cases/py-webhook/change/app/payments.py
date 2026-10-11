"""Payment provider integration."""

import hashlib
import hmac
import json
import os

import requests

from app.store import orders

WEBHOOK_SECRET = os.environ["PAYMENT_WEBHOOK_SECRET"].encode()


def sign(body: bytes) -> str:
    """Hex HMAC-SHA256 of a webhook body, as the provider computes it."""
    return hmac.new(WEBHOOK_SECRET, body, hashlib.sha256).hexdigest()


def mark_paid(order_id: str) -> None:
    orders[order_id]["status"] = "paid"


def handle_webhook(headers: dict, body: bytes) -> tuple:
    """Provider -> us. Reject anything not signed with the shared secret."""
    if headers.get("X-Signature", "") != sign(body):
        return 401, {"error": "bad signature"}
    event = json.loads(body)
    if event.get("type") == "payment.succeeded":
        mark_paid(event["order_id"])
    return 200, {"ok": True}


def send_test_event(merchant_id: str, url: str) -> tuple:
    """Merchant dashboard 'Send test event' button: POST a sample event to the callback URL the
    merchant typed and show them what their server answered."""
    sample = {"type": "payment.succeeded", "order_id": "test", "merchant_id": merchant_id}
    resp = requests.post(url, json=sample, timeout=5)
    return 200, {"status": resp.status_code, "body": resp.text[:2000]}
