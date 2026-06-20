"""Per-agent voice and prompt overrides for the ElevenLabs agent pool."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

@dataclass(frozen=True)
class AgentProfile:
    name: str
    gender: str
    voice_id: str


AGENT_PROFILES: dict[str, AgentProfile] = {
    "agent_6901kqvn0c4wfyntcdfbtf4jhhce": AgentProfile(
        name="Μαρίνα",
        gender="female",
        voice_id="GgG098SBTN4s6aDzzSlG",
    ),
    "agent_0701kvdqwxkkezfsckh22xgbje5e": AgentProfile(
        name="Ελένη",
        gender="female",
        voice_id="XrExE9yKIg1WjnnlVkGX",
    ),
    "agent_5701kvdqx74bfs9950k8v5ff0fmk": AgentProfile(
        name="Γιώργος",
        gender="male",
        voice_id="JBFqnCBsd6RMkjVDRZzb",
    ),
    "agent_9901kvdqxkr6f39vyh7arksb17f5": AgentProfile(
        name="Νίκος",
        gender="male",
        voice_id="onwK4e9ZLuTAKqWW03F9",
    ),
    "agent_4901kvdqxytdez3bmwdnrhqdfa4w": AgentProfile(
        name="Δημήτρης",
        gender="male",
        voice_id="M7wbvcEPy01YrxQfUBTw",
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
    """Female agents use default_path; male agents use the *_male variant."""
    base = Path(default_path)
    profile = profile_for_agent(agent_id)
    if profile and profile.gender == "male":
        return base.with_name(f"{base.stem}_male{base.suffix}")
    return base
