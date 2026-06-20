"""Registered prompt scenarios (persona + prompt file paths)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PromptScenario:
    id: str
    description: str
    system_prompt: str
    first_message: str
    requires_report: bool = False
    agent_gender: str | None = None


PROMPT_SCENARIOS: dict[str, PromptScenario] = {
    "parking_report": PromptScenario(
        id="parking_report",
        description="Worried citizen reporting illegal parking",
        system_prompt="prompts/worried_citizen_system.txt",
        first_message="prompts/worried_citizen_first_message.txt",
        requires_report=True,
    ),
    "cockroach_advocate": PromptScenario(
        id="cockroach_advocate",
        description="15 s pitch: urban cockroaches help the ecosystem",
        system_prompt="prompts/cockroach_advocate_system.txt",
        first_message="prompts/cockroach_advocate_first_message.txt",
        requires_report=False,
    ),
    "birthday_wish": PromptScenario(
        id="birthday_wish",
        description="Flirty birthday call from a female friend",
        system_prompt="prompts/birthday_wish_system.txt",
        first_message="prompts/birthday_wish_first_message.txt",
        requires_report=False,
        agent_gender="female",
    ),
}


def scenario_ids() -> list[str]:
    return list(PROMPT_SCENARIOS.keys())


def get_scenario(scenario_id: str) -> PromptScenario:
    key = scenario_id.strip()
    if key not in PROMPT_SCENARIOS:
        known = ", ".join(scenario_ids())
        raise ValueError(f"Unknown prompt scenario {scenario_id!r}. Choose one of: {known}")
    return PROMPT_SCENARIOS[key]


def format_scenario_choices() -> str:
    lines = []
    for scenario in PROMPT_SCENARIOS.values():
        lines.append(f"  {scenario.id} — {scenario.description}")
    return "\n".join(lines)
