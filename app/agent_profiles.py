"""Per-agent voice and prompt overrides for the ElevenLabs agent pool."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

FEMALE_PROMPT = "prompts/worried_citizen_system.txt"
MALE_PROMPT = "prompts/worried_citizen_system_male.txt"


@dataclass(frozen=True)
class AgentProfile:
    name: str
    gender: str
    voice_id: str
    prompt_path: str


AGENT_PROFILES: dict[str, AgentProfile] = {
    "agent_6901kqvn0c4wfyntcdfbtf4jhhce": AgentProfile(
        name="Μαρίνα",
        gender="female",
        voice_id="GgG098SBTN4s6aDzzSlG",
        prompt_path=FEMALE_PROMPT,
    ),
    "agent_0701kvdqwxkkezfsckh22xgbje5e": AgentProfile(
        name="Ελένη",
        gender="female",
        voice_id="XrExE9yKIg1WjnnlVkGX",
        prompt_path=FEMALE_PROMPT,
    ),
    "agent_5701kvdqx74bfs9950k8v5ff0fmk": AgentProfile(
        name="Γιώργος",
        gender="male",
        voice_id="JBFqnCBsd6RMkjVDRZzb",
        prompt_path=MALE_PROMPT,
    ),
    "agent_9901kvdqxkr6f39vyh7arksb17f5": AgentProfile(
        name="Νίκος",
        gender="male",
        voice_id="onwK4e9ZLuTAKqWW03F9",
        prompt_path=MALE_PROMPT,
    ),
    "agent_4901kvdqxytdez3bmwdnrhqdfa4w": AgentProfile(
        name="Δημήτρης",
        gender="male",
        voice_id="M7wbvcEPy01YrxQfUBTw",
        prompt_path=MALE_PROMPT,
    ),
}


def profile_for_agent(agent_id: str) -> AgentProfile | None:
    return AGENT_PROFILES.get(agent_id)


def format_agent_label(agent_id: str) -> str:
    """Agent id with display name when known, e.g. agent_… (Ελένη)."""
    profile = profile_for_agent(agent_id)
    if profile:
        return f"{agent_id} ({profile.name})"
    return agent_id


def prompt_path_for_agent(agent_id: str, default_path: str) -> Path:
    profile = profile_for_agent(agent_id)
    if profile:
        return Path(profile.prompt_path)
    return Path(default_path)
