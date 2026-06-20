"""Per-call prompt scenario passed from run_calls.py into the live agent."""

from __future__ import annotations

from app.config import Settings

_pending_by_phone: dict[str, str] = {}


def normalize_phone(phone: str) -> str:
    return phone.replace(" ", "")


def stash_scenario_for_phone(phone: str, scenario_id: str) -> None:
    _pending_by_phone[normalize_phone(phone)] = scenario_id


def pop_scenario_for_phone(phone: str, settings: Settings) -> str:
    return _pending_by_phone.pop(normalize_phone(phone), settings.prompt_scenario)
