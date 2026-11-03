"""Public URL of a stop, encoded in its QR (stop_tokens_qr design §2, AC-06)."""


def build_stop_url(base_url: str, stop_id: str, token: str) -> str:
    """`{base_url}/p/{stop_id}?t={token}` with no duplicated slash after the base URL."""
    return f"{base_url.rstrip('/')}/p/{stop_id}?t={token}"
