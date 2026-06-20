"""Pass outbound call context from run_calls.py to the API server via webhook URL."""

from __future__ import annotations

from urllib.parse import urlencode

from starlette.requests import Request

from app.agent_context import pop_agent_for_phone, resolve_agent_id
from app.config import Settings
from app.prompt_scenarios import PromptScenario, get_scenario
from app.report_context import CallReportDetails, pop_report_for_phone
from app.scenario_context import pop_scenario_for_phone


def build_voice_webhook_url(
    settings: Settings,
    *,
    scenario: PromptScenario,
    agent_id: str,
    report: CallReportDetails,
) -> str:
    """Embed scenario/agent/report in the Twilio webhook URL (cross-process safe)."""
    params: dict[str, str] = {
        "prompt_scenario": scenario.id,
        "agent_id": agent_id,
    }
    if scenario.requires_report:
        params.update(report.as_stream_parameters())
    query = urlencode(params)
    return f"{settings.public_base_url.rstrip('/')}/voice/inbound?{query}"


def _report_from_query(query_params, settings: Settings) -> CallReportDetails | None:
    keys = ("report_location", "report_plate", "report_car_color", "report_car_brand")
    if not any(query_params.get(key) for key in keys):
        return None
    defaults = CallReportDetails.from_settings(settings)
    return CallReportDetails(
        location=(query_params.get("report_location") or defaults.location).strip(),
        plate=(query_params.get("report_plate") or defaults.plate).strip(),
        car_color=(query_params.get("report_car_color") or defaults.car_color).strip(),
        car_brand=(query_params.get("report_car_brand") or defaults.car_brand).strip(),
    )


def resolve_inbound_context(
    request: Request,
    to_number: str,
    settings: Settings,
) -> tuple[str, str, CallReportDetails]:
    """Read call context from webhook query params, else in-memory stash (same process)."""
    query = request.query_params

    scenario_id = (query.get("prompt_scenario") or "").strip()
    if not scenario_id:
        scenario_id = pop_scenario_for_phone(to_number, settings)
    scenario = get_scenario(scenario_id)

    report = _report_from_query(query, settings) or pop_report_for_phone(
        to_number, settings
    )

    stream_agent_id = (query.get("agent_id") or "").strip()
    if stream_agent_id:
        agent_id = resolve_agent_id(
            stream_agent_id, settings, gender=scenario.agent_gender
        )
    else:
        agent_id = pop_agent_for_phone(
            to_number, settings, gender=scenario.agent_gender
        )

    return scenario.id, agent_id, report
