from pathlib import Path
from uuid import uuid4

import httpx

from app.config import Settings


def _voice_id_for_language(settings: Settings, language: str) -> str:
    if language.lower().startswith("el"):
        return settings.elevenlabs_voice_id_el
    return settings.elevenlabs_voice_id_en


def synthesize_to_file(
    settings: Settings,
    text: str,
    language: str,
    output_dir: Path,
    filename_prefix: str,
) -> str:
    output_dir.mkdir(parents=True, exist_ok=True)
    voice_id = _voice_id_for_language(settings, language)
    target_name = f"{filename_prefix}-{uuid4().hex[:8]}.mp3"
    target_path = output_dir / target_name

    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
    headers = {
        "xi-api-key": settings.elevenlabs_api_key,
        "accept": "audio/mpeg",
        "content-type": "application/json",
    }
    payload = {
        "text": text,
        "model_id": settings.elevenlabs_model_id,
        "voice_settings": {"stability": 0.45, "similarity_boost": 0.75},
    }

    with httpx.Client(timeout=30.0) as client:
        response = client.post(url, headers=headers, json=payload)
        response.raise_for_status()
        target_path.write_bytes(response.content)

    return target_name
