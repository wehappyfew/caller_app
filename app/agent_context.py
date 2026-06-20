"""Per-call ElevenLabs agent selection (random persona from configured pool)."""

from __future__ import annotations

import random

from app.agent_profiles import profile_for_agent
from app.config import Settings
from app.report_context import normalize_phone

_pending_by_phone: dict[str, str] = {}


def agent_ids_from_settings(settings: Settings, *, gender: str | None = None) -> list[str]:
    ids: list[str] = []
    if settings.elevenlabs_agent_ids.strip():
        ids = [
            part.strip()
            for part in settings.elevenlabs_agent_ids.split(",")
            if part.strip()
        ]
    elif settings.elevenlabs_agent_id.strip():
        ids = [settings.elevenlabs_agent_id.strip()]
    if gender:
        ids = [
            agent_id
            for agent_id in ids
            if (profile := profile_for_agent(agent_id)) and profile.gender == gender
        ]
    return ids


def pick_random_agent_id(settings: Settings, *, gender: str | None = None) -> str:
    ids = agent_ids_from_settings(settings, gender=gender)
    if not ids:
        if gender:
            raise ValueError(
                f"No ElevenLabs agent IDs configured for gender {gender!r}"
            )
        raise ValueError("No ElevenLabs agent IDs configured")
    return random.choice(ids)


def stash_agent_for_phone(phone: str, agent_id: str) -> None:
    _pending_by_phone[normalize_phone(phone)] = agent_id


def pop_agent_for_phone(
    phone: str, settings: Settings, *, gender: str | None = None
) -> str:
    return _pending_by_phone.pop(
        normalize_phone(phone),
        pick_random_agent_id(settings, gender=gender),
    )


def resolve_agent_id(
    agent_id: str,
    settings: Settings,
    *,
    gender: str | None = None,
) -> str:
    """Use agent_id when it matches gender; otherwise pick from the filtered pool."""
    agent_id = agent_id.strip()
    if not gender:
        return agent_id or pick_random_agent_id(settings)
    profile = profile_for_agent(agent_id) if agent_id else None
    if profile and profile.gender == gender:
        return agent_id
    return pick_random_agent_id(settings, gender=gender)
