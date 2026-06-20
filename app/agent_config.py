"""ElevenLabs agent persona and sync from app settings."""

from __future__ import annotations

import logging
from pathlib import Path

from elevenlabs import ElevenLabs
from elevenlabs.conversational_ai.conversation import ConversationInitiationData
from elevenlabs.types import ConversationalConfig

from app.agent_context import agent_ids_from_settings
from app.agent_profiles import profile_for_agent, prompt_path_for_agent
from app.config import Settings
from app.prompt_scenarios import PromptScenario, get_scenario
from app.report_context import CallReportDetails

logger = logging.getLogger("caller_app")

DEFAULT_PROMPT_PATH = Path("prompts/worried_citizen_system.txt")
DEFAULT_FIRST_MESSAGE_PATH = Path("prompts/worried_citizen_first_message.txt")


def _read_text_file(path: Path) -> str:
    if not path.exists():
        raise FileNotFoundError(f"Agent prompt file not found: {path}")
    return path.read_text(encoding="utf-8").strip()


def resolve_scenario(settings: Settings, scenario_id: str | None = None) -> PromptScenario:
    return get_scenario(scenario_id or settings.prompt_scenario)


def load_first_message(settings: Settings, scenario_id: str | None = None) -> str:
    if settings.elevenlabs_agent_first_message.strip():
        return settings.elevenlabs_agent_first_message.strip()
    scenario = resolve_scenario(settings, scenario_id)
    return _read_text_file(Path(scenario.first_message))


def load_system_prompt(
    settings: Settings,
    scenario_id: str | None = None,
    *,
    agent_id: str = "",
) -> str:
    if settings.elevenlabs_agent_system_prompt.strip():
        return settings.elevenlabs_agent_system_prompt.strip()
    scenario = resolve_scenario(settings, scenario_id)
    path = prompt_path_for_agent(agent_id, scenario.system_prompt)
    return _read_text_file(path)


def load_agent_first_message(settings: Settings) -> str:
    return load_first_message(settings)


def load_agent_system_prompt(settings: Settings) -> str:
    return load_system_prompt(settings)


def report_dynamic_variables(
    settings: Settings,
    *,
    notes: str = "",
    report: CallReportDetails | None = None,
) -> dict[str, str]:
    details = report or CallReportDetails.from_settings(settings)
    return {
        "contact_name": "",
        "language": settings.elevenlabs_agent_language,
        "notes": notes,
        **details.as_dynamic_variables(),
    }


def build_conversation_init(
    settings: Settings,
    *,
    contact_name: str,
    language: str,
    notes: str,
    report: CallReportDetails | None = None,
    scenario_id: str | None = None,
    agent_id: str = "",
) -> ConversationInitiationData:
    """Runtime context for one call (dynamic variables for the agent prompt)."""
    variables = report_dynamic_variables(settings, notes=notes, report=report)
    variables["contact_name"] = contact_name
    variables["language"] = language

    effective_scenario = scenario_id or settings.prompt_scenario

    if not settings.elevenlabs_use_runtime_overrides:
        return ConversationInitiationData(dynamic_variables=variables)

    override: dict = {
        "agent": {
            "language": language if language else settings.elevenlabs_agent_language,
            "first_message": load_first_message(settings, effective_scenario),
            "prompt": {
                "prompt": load_system_prompt(
                    settings, effective_scenario, agent_id=agent_id
                ),
                "llm": settings.elevenlabs_agent_llm,
            },
        },
    }
    return ConversationInitiationData(
        dynamic_variables=variables,
        conversation_config_override=override,
    )


def sync_agent_from_settings(
    settings: Settings, scenario_id: str | None = None, *, force: bool = False
) -> None:
    """Push prompt, first message, and LLM from app config to the ElevenLabs agent."""
    if not force and not settings.elevenlabs_sync_agent_on_startup:
        logger.info("ElevenLabs agent sync skipped (ELEVENLABS_SYNC_AGENT_ON_STARTUP=false)")
        return

    scenario = resolve_scenario(settings, scenario_id)
    agent_ids = agent_ids_from_settings(settings, gender=scenario.agent_gender)
    if not agent_ids:
        logger.warning(
            "ElevenLabs agent sync skipped: no agent IDs for scenario %s (gender=%s)",
            scenario.id,
            scenario.agent_gender,
        )
        return

    client = ElevenLabs(api_key=settings.elevenlabs_api_key)
    first_message = load_first_message(settings, scenario.id)

    for agent_id in agent_ids:
        agent = client.conversational_ai.agents.get(agent_id=agent_id)
        profile = profile_for_agent(agent_id)
        prompt_text = load_system_prompt(settings, scenario.id, agent_id=agent_id)
        config_data = agent.conversation_config.model_dump()
        config_data["agent"]["first_message"] = first_message
        config_data["agent"]["language"] = settings.elevenlabs_agent_language
        config_data["agent"]["prompt"]["prompt"] = prompt_text
        config_data["agent"]["prompt"]["llm"] = settings.elevenlabs_agent_llm
        if profile:
            config_data["tts"]["voice_id"] = profile.voice_id

        conversation_config = ConversationalConfig.model_validate(config_data)
        update_kwargs: dict = {
            "agent_id": agent_id,
            "conversation_config": conversation_config,
        }
        if profile:
            update_kwargs["name"] = profile.name
        updated = client.conversational_ai.agents.update(**update_kwargs)
        logger.info(
            "Synced ElevenLabs agent %s (%s): scenario=%s llm=%s language=%s voice=%s",
            agent_id,
            profile.name if profile else agent_id,
            scenario.id,
            updated.conversation_config.agent.prompt.llm,
            updated.conversation_config.agent.language,
            updated.conversation_config.tts.voice_id,
        )
