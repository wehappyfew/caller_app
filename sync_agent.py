#!/usr/bin/env python3
"""Push agent prompt/LLM settings from .env and prompt files to ElevenLabs."""

import argparse

from app.agent_config import resolve_scenario, sync_agent_from_settings
from app.agent_context import agent_ids_from_settings
from app.agent_profiles import AGENT_PROFILES
from app.config import get_settings
from app.prompt_scenarios import format_scenario_choices, scenario_ids


def _parse_args() -> argparse.Namespace:
    settings = get_settings()
    parser = argparse.ArgumentParser(
        description="Sync ElevenLabs agents with prompt files from this repo.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Available scenarios:\n" + format_scenario_choices(),
    )
    parser.add_argument(
        "--scenario",
        choices=scenario_ids(),
        default=None,
        help=f"Prompt scenario to sync (default: PROMPT_SCENARIO in .env, currently {settings.prompt_scenario!r})",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    get_settings.cache_clear()
    settings = get_settings()
    scenario = resolve_scenario(settings, args.scenario)
    sync_agent_from_settings(settings, scenario.id, force=True)
    agent_ids = agent_ids_from_settings(settings, gender=scenario.agent_gender)
    print(f"Synced {len(agent_ids)} agent(s) for scenario {scenario.id}")
    for agent_id in agent_ids:
        profile = AGENT_PROFILES.get(agent_id)
        label = f"{profile.name} ({profile.gender})" if profile else agent_id
        print(f"  - {label}: {agent_id}")
    print(f"  LLM: {settings.elevenlabs_agent_llm}")
    print(f"  Language: {settings.elevenlabs_agent_language}")
    print(f"  System prompt: {scenario.system_prompt}")
    print(f"  First message: {scenario.first_message}")


if __name__ == "__main__":
    main()
