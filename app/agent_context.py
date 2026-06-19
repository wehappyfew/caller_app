"""Per-call ElevenLabs agent selection (random persona from configured pool)."""

from __future__ import annotations

import random

from app.config import Settings
from app.report_context import normalize_phone

_pending_by_phone: dict[str, str] = {}


def agent_ids_from_settings(settings: Settings) -> list[str]:
    if settings.elevenlabs_agent_ids.strip():
        return [
            part.strip()
            for part in settings.elevenlabs_agent_ids.split(",")
            if part.strip()
        ]
    if settings.elevenlabs_agent_id.strip():
        return [settings.elevenlabs_agent_id.strip()]
    return []


def pick_random_agent_id(settings: Settings) -> str:
    ids = agent_ids_from_settings(settings)
    if not ids:
        raise ValueError("No ElevenLabs agent IDs configured")
    return random.choice(ids)


def stash_agent_for_phone(phone: str, agent_id: str) -> None:
    _pending_by_phone[normalize_phone(phone)] = agent_id


def pop_agent_for_phone(phone: str, settings: Settings) -> str:
    return _pending_by_phone.pop(
        normalize_phone(phone),
        pick_random_agent_id(settings),
    )
