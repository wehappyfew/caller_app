#!/usr/bin/env python3
"""Push agent prompt/LLM settings from .env and prompt files to ElevenLabs."""

from app.agent_config import sync_agent_from_settings
from app.agent_context import agent_ids_from_settings
from app.agent_profiles import AGENT_PROFILES
from app.config import get_settings


def main() -> None:
    get_settings.cache_clear()
    settings = get_settings()
    sync_agent_from_settings(settings)
    agent_ids = agent_ids_from_settings(settings)
    print(f"Synced {len(agent_ids)} agent(s)")
    for agent_id in agent_ids:
        profile = AGENT_PROFILES.get(agent_id)
        label = f"{profile.name} ({profile.gender})" if profile else agent_id
        print(f"  - {label}: {agent_id}")
    print(f"  LLM: {settings.elevenlabs_agent_llm}")
    print(f"  Language: {settings.elevenlabs_agent_language}")
    print(f"  Prompt: {settings.elevenlabs_agent_prompt_path}")


if __name__ == "__main__":
    main()
