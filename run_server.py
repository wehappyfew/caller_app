#!/usr/bin/env python3
"""Start the caller_app API server with optional prompt scenario selection."""

from __future__ import annotations

import argparse
import os

import uvicorn

from app.config import get_settings
from app.prompt_scenarios import format_scenario_choices, get_scenario, scenario_ids


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Start the caller_app FastAPI server.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Available scenarios:\n" + format_scenario_choices(),
    )
    parser.add_argument(
        "--scenario",
        choices=scenario_ids(),
        default=None,
        help="Prompt scenario to sync on startup (overrides PROMPT_SCENARIO in .env)",
    )
    parser.add_argument("--host", default=None, help="Bind host (default: APP_HOST from .env)")
    parser.add_argument("--port", type=int, default=None, help="Bind port (default: APP_PORT from .env)")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    if args.scenario:
        os.environ["PROMPT_SCENARIO"] = args.scenario

    get_settings.cache_clear()
    settings = get_settings()
    scenario = get_scenario(settings.prompt_scenario)

    host = args.host or settings.app_host
    port = args.port or settings.app_port

    print(f"Starting caller_app on {host}:{port}")
    print(f"Prompt scenario: {scenario.id} — {scenario.description}")
    print(f"  system: {scenario.system_prompt}")
    print(f"  first message: {scenario.first_message}")

    uvicorn.run("app.main:app", host=host, port=port)


if __name__ == "__main__":
    main()
