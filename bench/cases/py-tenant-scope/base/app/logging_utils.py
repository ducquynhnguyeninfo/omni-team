REDACT = {"authorization", "cookie", "x-api-key"}


def safe_headers(headers: dict) -> dict:
    return {k: ("[redacted]" if k.lower() in REDACT else v) for k, v in headers.items()}
