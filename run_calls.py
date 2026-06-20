import argparse
import time
from urllib.error import HTTPError, URLError
from urllib.request import urlopen

from app.agent_context import pick_random_agent_id
from app.agent_profiles import format_agent_label
from app.agent_config import sync_agent_from_settings
from app.call_costs import build_call_cost_summary, wait_for_twilio_call_final
from app.config import get_settings
from app.outbound_context import build_voice_webhook_url
from app.preflight import check_call_server_ready
from app.csv_store import ContactSelectionError, resolve_contact_to_call
from app.prompt_scenarios import format_scenario_choices, get_scenario, scenario_ids
from app.report_context import CallReportDetails
from app.twilio_client import (
    TERMINAL_CALL_STATUSES,
    get_twilio_client,
    ring_timeout_seconds,
    stop_call,
    watch_call_progress,
)


def _parse_args() -> argparse.Namespace:
    settings = get_settings()
    defaults = CallReportDetails.from_settings(settings)
    parser = argparse.ArgumentParser(
        description="Place an outbound call to the active contact in the CSV.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Available scenarios:\n" + format_scenario_choices(),
    )
    parser.add_argument(
        "--contact",
        default=None,
        help="Contact name from CSV (default: CALL_CONTACT in .env)",
    )
    parser.add_argument(
        "--scenario",
        choices=scenario_ids(),
        default=None,
        help=f"Prompt scenario for this call (default: PROMPT_SCENARIO in .env, currently {settings.prompt_scenario!r})",
    )
    parser.add_argument(
        "--location",
        default=None,
        help=f"Illegal parking location (default from .env: {defaults.location})",
    )
    parser.add_argument(
        "--plate",
        default=None,
        help=f"License plate, Greek capitals (default: {defaults.plate})",
    )
    parser.add_argument(
        "--color",
        dest="car_color",
        default=None,
        help=f"Car color (default: {defaults.car_color})",
    )
    parser.add_argument(
        "--brand",
        dest="car_brand",
        default=None,
        help=f"Car make/brand (default: {defaults.car_brand})",
    )
    return parser.parse_args()


def _resolve_report(args: argparse.Namespace, settings) -> CallReportDetails:
    defaults = CallReportDetails.from_settings(settings)
    return CallReportDetails(
        location=args.location if args.location is not None else defaults.location,
        plate=args.plate if args.plate is not None else defaults.plate,
        car_color=args.car_color if args.car_color is not None else defaults.car_color,
        car_brand=args.car_brand if args.car_brand is not None else defaults.car_brand,
    )


def _wait_for_call_summary(settings, call_sid: str) -> str | None:
    """Poll local API server for cost summary written when the call ends."""
    url = f"http://127.0.0.1:{settings.app_port}/debug/call-summary/{call_sid}"
    deadline = time.time() + 600
    while time.time() < deadline:
        try:
            with urlopen(url, timeout=2) as response:
                body = response.read().decode("utf-8").strip()
                if body:
                    return body
        except HTTPError as exc:
            if exc.code != 404:
                break
        except URLError:
            break
        time.sleep(2)
    return None


def _print_post_call_summary(
    settings, client, call_sid: str, contact_name: str
) -> None:
    print("\nWaiting for call to finish...")
    call = watch_call_progress(
        client,
        call_sid,
        contact_name,
        max_rings=settings.call_max_rings,
        ring_seconds=settings.call_ring_seconds,
    )
    if call.status not in TERMINAL_CALL_STATUSES:
        call = wait_for_twilio_call_final(client, call_sid)
    print(f"Call status: {call.status}")

    summary_text = _wait_for_call_summary(settings, call_sid)
    if summary_text:
        print(f"\n{summary_text}")
        return

    try:
        summary = build_call_cost_summary(
            settings,
            call_sid=call_sid,
            conversation_id=None,
            twilio_client=client,
            wait_for_twilio=False,
        )
        print(f"\n{summary.as_table()}")
        if summary.conversation_id is None:
            print("(ElevenLabs line is partial — full summary is in the API server log.)")
    except Exception as exc:
        print(f"\nCould not fetch cost summary: {exc}")


def main() -> None:
    args = _parse_args()
    settings = get_settings()
    scenario = get_scenario(args.scenario or settings.prompt_scenario)
    report = _resolve_report(args, settings)
    if scenario.requires_report:
        missing = report.missing_fields()
        if missing:
            print("Cannot place calls.")
            print(report.format_missing_message())
            raise SystemExit(1)

    contact_name = (args.contact or settings.call_contact or "").strip() or None
    try:
        contact = resolve_contact_to_call(settings.csv_path, contact_name)
    except ContactSelectionError as exc:
        print(f"Cannot place call: {exc}")
        raise SystemExit(1) from None

    preflight_errors = check_call_server_ready(settings)
    if preflight_errors:
        print("Cannot place call — server or tunnel is not ready:")
        for message in preflight_errors:
            print(f"  - {message}")
        raise SystemExit(1)

    client = get_twilio_client(settings)

    print(f"Prompt scenario: {scenario.id} — {scenario.description}")
    if scenario.agent_gender:
        print(f"Agent pool: {scenario.agent_gender} only")
    if scenario.requires_report:
        print("Report details for this run:")
        print(f"  location: {report.location}")
        print(f"  plate:    {report.plate}")
        print(f"  color:    {report.car_color}")
        print(f"  brand:    {report.car_brand}")
    print(f"\nCalling {contact.name} ({contact.phone})...")

    if (
        scenario.id != settings.prompt_scenario
        and not settings.elevenlabs_use_runtime_overrides
    ):
        print(
            f"Syncing ElevenLabs agents to scenario {scenario.id!r} "
            f"(server default is {settings.prompt_scenario!r})..."
        )
        sync_agent_from_settings(settings, scenario.id, force=True)

    agent_id = pick_random_agent_id(settings, gender=scenario.agent_gender)
    webhook_url = build_voice_webhook_url(
        settings,
        scenario=scenario,
        agent_id=agent_id,
        report=report,
    )
    answer_timeout = ring_timeout_seconds(settings)
    call = client.calls.create(
        to=contact.phone,
        from_=settings.twilio_from_number,
        url=webhook_url,
        method="POST",
        timeout=answer_timeout,
    )
    print(f"Dialing {contact.name} ({contact.phone})")
    print(f"SID: {call.sid}")
    print(f"agent: {format_agent_label(agent_id)}")

    try:
        _print_post_call_summary(settings, client, call.sid, contact.name)
    except KeyboardInterrupt:
        print()
        stop_call(client, call.sid, contact_name=contact.name)
        raise SystemExit(130) from None


if __name__ == "__main__":
    main()
