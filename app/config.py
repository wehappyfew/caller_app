from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    app_env: str = Field(default="development", alias="APP_ENV")
    app_host: str = Field(default="0.0.0.0", alias="APP_HOST")
    app_port: int = Field(default=8001, alias="APP_PORT")
    public_base_url: str = Field(alias="PUBLIC_BASE_URL")

    twilio_account_sid: str = Field(alias="TWILIO_ACCOUNT_SID")
    twilio_auth_token: str = Field(alias="TWILIO_AUTH_TOKEN")
    twilio_api_key_sid: str = Field(default="", alias="TWILIO_API_KEY_SID")
    twilio_from_number: str = Field(alias="TWILIO_FROM_NUMBER")

    elevenlabs_api_key: str = Field(alias="ELEVENLABS_API_KEY")
    elevenlabs_agent_id: str = Field(default="", alias="ELEVENLABS_AGENT_ID")
    elevenlabs_agent_ids: str = Field(default="", alias="ELEVENLABS_AGENT_IDS")
    elevenlabs_agent_llm: str = Field(
        default="gemini-2.5-flash", alias="ELEVENLABS_AGENT_LLM"
    )
    elevenlabs_agent_language: str = Field(default="el", alias="ELEVENLABS_AGENT_LANGUAGE")
    elevenlabs_agent_prompt_path: str = Field(
        default="prompts/worried_citizen_system.txt",
        alias="ELEVENLABS_AGENT_PROMPT_PATH",
    )
    elevenlabs_agent_first_message_path: str = Field(
        default="prompts/worried_citizen_first_message.txt",
        alias="ELEVENLABS_AGENT_FIRST_MESSAGE_PATH",
    )
    elevenlabs_agent_system_prompt: str = Field(
        default="", alias="ELEVENLABS_AGENT_SYSTEM_PROMPT"
    )
    elevenlabs_agent_first_message: str = Field(
        default="", alias="ELEVENLABS_AGENT_FIRST_MESSAGE"
    )
    elevenlabs_sync_agent_on_startup: bool = Field(
        default=True, alias="ELEVENLABS_SYNC_AGENT_ON_STARTUP"
    )
    elevenlabs_use_runtime_overrides: bool = Field(
        default=False, alias="ELEVENLABS_USE_RUNTIME_OVERRIDES"
    )
    elevenlabs_voice_id_el: str = Field(default="", alias="ELEVENLABS_VOICE_ID_EL")
    elevenlabs_voice_id_en: str = Field(default="", alias="ELEVENLABS_VOICE_ID_EN")

    report_location: str = Field(
        default="Mitrou Sarkoudinou 7, Neos Kosmos, Athens",
        alias="REPORT_LOCATION",
    )
    report_plate: str = Field(default="ΙΗΧ9037", alias="REPORT_PLATE")
    report_car_color: str = Field(default="κόκκινο", alias="REPORT_CAR_COLOR")
    report_car_brand: str = Field(default="Mercedes", alias="REPORT_CAR_BRAND")

    csv_path: str = Field(default="data/contacts.csv", alias="CSV_PATH")
    call_contact: str = Field(default="", alias="CALL_CONTACT")
    call_logs_dir: str = Field(default="call_logs", alias="CALL_LOGS_DIR")
    timezone: str = Field(default="Europe/Athens", alias="TIMEZONE")
    max_turns: int = Field(default=3, alias="MAX_TURNS")
    call_timeout_seconds: int = Field(default=60, alias="CALL_TIMEOUT_SECONDS")
    call_max_rings: int = Field(default=4, alias="CALL_MAX_RINGS")
    call_ring_seconds: float = Field(default=5.0, alias="CALL_RING_SECONDS")


@lru_cache
def get_settings() -> Settings:
    return Settings()
