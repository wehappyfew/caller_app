"""Checks that the local API and public tunnel are ready before placing a call."""

from __future__ import annotations

import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from app.config import Settings


def _fetch_health(url: str, *, timeout: float) -> tuple[bool, str]:
    request = Request(url, headers={"User-Agent": "caller_app-preflight"})
    try:
        with urlopen(request, timeout=timeout) as response:
            body = response.read().decode("utf-8", errors="replace").strip()
    except HTTPError as exc:
        snippet = exc.read().decode("utf-8", errors="replace")[:120]
        return False, f"HTTP {exc.code} ({snippet or exc.reason})"
    except URLError as exc:
        return False, str(exc.reason or exc)

    try:
        payload = json.loads(body) if body else {}
    except json.JSONDecodeError:
        return False, f"not JSON: {body[:120]!r}"

    if payload.get("status") == "ok":
        return True, "ok"
    return False, f"unexpected body: {body[:120]!r}"


def check_call_server_ready(settings: Settings) -> list[str]:
    """Return human-readable errors; empty list means ready to dial."""
    errors: list[str] = []
    local_url = f"http://127.0.0.1:{settings.app_port}/health"
    public_url = f"{settings.public_base_url.rstrip('/')}/health"

    ok, detail = _fetch_health(local_url, timeout=3)
    if not ok:
        errors.append(
            f"Local API not healthy at {local_url} ({detail}). "
            f"Start: uvicorn app.main:app --host 0.0.0.0 --port {settings.app_port}. "
            "If ComfyUI or another app uses port 8000, use 8001 instead."
        )

    ok, detail = _fetch_health(public_url, timeout=8)
    if not ok:
        errors.append(
            f"Public URL not healthy at {public_url} ({detail}). "
            f"Run ngrok http 127.0.0.1:{settings.app_port} and set PUBLIC_BASE_URL in .env "
            "to the new https URL (no trailing slash)."
        )

    return errors
