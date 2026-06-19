"""Fetch per-call costs and account balances for Twilio and ElevenLabs."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass

from elevenlabs import ElevenLabs
from elevenlabs.core.api_error import ApiError

from app.config import Settings
from app.twilio_client import TERMINAL_CALL_STATUSES, get_twilio_client

logger = logging.getLogger("caller_app")


@dataclass(frozen=True)
class ServiceCostRow:
    service: str
    call_cost: str
    balance_remaining: str


@dataclass(frozen=True)
class CallCostSummary:
    call_sid: str
    conversation_id: str | None
    rows: list[ServiceCostRow]

    def as_table(self) -> str:
        headers = ("Service", "This call", "Balance remaining")
        col_widths = [
            max(len(headers[0]), max((len(r.service) for r in self.rows), default=0)),
            max(len(headers[1]), max((len(r.call_cost) for r in self.rows), default=0)),
            max(len(headers[2]), max((len(r.balance_remaining) for r in self.rows), default=0)),
        ]

        def fmt_row(cells: tuple[str, str, str]) -> str:
            return " | ".join(cell.ljust(width) for cell, width in zip(cells, col_widths, strict=True))

        divider = "-+-".join("-" * width for width in col_widths)
        lines = [
            f"Call cost summary ({self.call_sid})",
            fmt_row(headers),
            divider,
        ]
        lines.extend(fmt_row((row.service, row.call_cost, row.balance_remaining)) for row in self.rows)
        if self.conversation_id:
            lines.append(f"ElevenLabs conversation: {self.conversation_id}")
        return "\n".join(lines)


def _format_twilio_price(price: str | None, price_unit: str | None, duration: int | str | None) -> str:
    if price is None:
        duration_part = f", {duration}s" if duration is not None else ""
        return f"pending{duration_part}"
    amount = abs(float(price))
    unit = price_unit or "USD"
    duration_part = f", {duration}s" if duration is not None else ""
    return f"${amount:.4f} {unit}{duration_part}"


def wait_for_twilio_call_final(
    client: Client,
    call_sid: str,
    *,
    timeout_seconds: int = 600,
    poll_seconds: float = 2.0,
):
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        call = client.calls(call_sid).fetch()
        if call.status in TERMINAL_CALL_STATUSES:
            if call.price is not None or call.status != "completed":
                return call
        time.sleep(poll_seconds)
    return client.calls(call_sid).fetch()


def _fetch_twilio_balance(client: Client, settings: Settings) -> str:
    try:
        balance = client.api.v2010.accounts(settings.twilio_account_sid).balance.fetch()
        return f"${float(balance.balance):.4f} {balance.currency}"
    except Exception as exc:
        logger.warning("Failed to fetch Twilio balance: %s", exc)
        return "unavailable"


def _fetch_elevenlabs_balance(client: ElevenLabs) -> str:
    try:
        sub = client.user.subscription.get()
        remaining = max(sub.character_limit - sub.character_count, 0)
        return f"{remaining:,} credits ({sub.tier} plan)"
    except ApiError as exc:
        if "user_read" in str(exc):
            return "n/a (add user_read to ElevenLabs API key)"
        logger.warning("Failed to fetch ElevenLabs balance: %s", exc)
        return "unavailable"
    except Exception as exc:
        logger.warning("Failed to fetch ElevenLabs balance: %s", exc)
        return "unavailable"


def _fetch_elevenlabs_call_cost(
    client: ElevenLabs,
    conversation_id: str | None,
) -> tuple[str, str | None]:
    if not conversation_id:
        return "n/a (no conversation id)", None

    try:
        for attempt in range(6):
            conv = client.conversational_ai.conversations.get(conversation_id=conversation_id)
            metadata = conv.metadata
            if metadata and metadata.cost is not None:
                duration = metadata.call_duration_secs
                charging = metadata.charging
                credits = metadata.cost
                parts = [f"{credits:,} credits"]
                if duration is not None:
                    parts.append(f"{duration}s")
                if charging and charging.llm_price is not None:
                    parts.append(f"LLM ${charging.llm_price:.4f}")
                return " · ".join(parts), conversation_id
            time.sleep(2)
        return "pending", conversation_id
    except Exception as exc:
        logger.warning("Failed to fetch ElevenLabs conversation cost: %s", exc)
        return "unavailable", conversation_id


def build_call_cost_summary(
    settings: Settings,
    *,
    call_sid: str,
    conversation_id: str | None,
    twilio_client: Client | None = None,
    elevenlabs_client: ElevenLabs | None = None,
    wait_for_twilio: bool = True,
) -> CallCostSummary:
    twilio_client = twilio_client or get_twilio_client(settings)
    elevenlabs_client = elevenlabs_client or ElevenLabs(api_key=settings.elevenlabs_api_key)

    if wait_for_twilio:
        time.sleep(2)
        call = wait_for_twilio_call_final(twilio_client, call_sid)
    else:
        call = twilio_client.calls(call_sid).fetch()

    twilio_call_cost = _format_twilio_price(call.price, call.price_unit, call.duration)
    twilio_balance = _fetch_twilio_balance(twilio_client, settings)

    elevenlabs_call_cost, conv_id = _fetch_elevenlabs_call_cost(elevenlabs_client, conversation_id)
    elevenlabs_balance = _fetch_elevenlabs_balance(elevenlabs_client)

    return CallCostSummary(
        call_sid=call_sid,
        conversation_id=conv_id or conversation_id,
        rows=[
            ServiceCostRow("Twilio", twilio_call_cost, twilio_balance),
            ServiceCostRow("ElevenLabs", elevenlabs_call_cost, elevenlabs_balance),
        ],
    )


def log_call_cost_summary(summary: CallCostSummary) -> None:
    logger.info("\n%s", summary.as_table())
