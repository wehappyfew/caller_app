from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    app_env: str = Field(default="development", alias="APP_ENV")
    app_host: str = Field(default="0.0.0.0", alias="APP_HOST")
    app_port: int = Field(default=8000, alias="APP_PORT")
    public_base_url: str = Field(alias="PUBLIC_BASE_URL")

    twilio_account_sid: str = Field(alias="TWILIO_ACCOUNT_SID")
    twilio_auth_token: str = Field(alias="TWILIO_AUTH_TOKEN")
    twilio_from_number: str = Field(alias="TWILIO_FROM_NUMBER")

    elevenlabs_api_key: str = Field(alias="ELEVENLABS_API_KEY")
    elevenlabs_voice_id_el: str = Field(alias="ELEVENLABS_VOICE_ID_EL")
    elevenlabs_voice_id_en: str = Field(alias="ELEVENLABS_VOICE_ID_EN")
    elevenlabs_model_id: str = Field(default="eleven_multilingual_v2", alias="ELEVENLABS_MODEL_ID")

    csv_path: str = Field(default="data/contacts.csv", alias="CSV_PATH")
    timezone: str = Field(default="Europe/Athens", alias="TIMEZONE")
    max_turns: int = Field(default=3, alias="MAX_TURNS")
    call_timeout_seconds: int = Field(default=60, alias="CALL_TIMEOUT_SECONDS")


@lru_cache
def get_settings() -> Settings:
    return Settings()
