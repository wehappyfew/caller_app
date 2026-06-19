"""Bridge between Twilio Media Streams and the ElevenLabs Conversational AI SDK.

Twilio Media Streams sends and expects μ-law 8 kHz audio. The current
ElevenLabs agent is configured for PCM 16 kHz, so this bridge transcodes both
directions to avoid static/noise on the phone call.
"""

import asyncio
import base64
import json
import struct

from elevenlabs.conversational_ai.conversation import AudioInterface
from fastapi import WebSocket
from starlette.websockets import WebSocketDisconnect, WebSocketState

BIAS = 0x84
CLIP = 32635


def _ulaw_byte_to_pcm16(byte: int) -> int:
    byte = ~byte & 0xFF
    sign = byte & 0x80
    exponent = (byte >> 4) & 0x07
    mantissa = byte & 0x0F
    sample = ((mantissa << 3) + BIAS) << exponent
    sample -= BIAS
    return -sample if sign else sample


def _pcm16_to_ulaw_byte(sample: int) -> int:
    sign = 0x80 if sample < 0 else 0
    if sample < 0:
        sample = -sample
    sample = min(sample, CLIP) + BIAS

    exponent = 7
    mask = 0x4000
    while exponent > 0 and not (sample & mask):
        exponent -= 1
        mask >>= 1
    mantissa = (sample >> (exponent + 3)) & 0x0F
    return ~(sign | (exponent << 4) | mantissa) & 0xFF


def _mulaw_8k_to_pcm16_16k(audio: bytes) -> bytes:
    """Decode Twilio μ-law 8 kHz and upsample to PCM16 little-endian 16 kHz."""
    samples_8k = [_ulaw_byte_to_pcm16(byte) for byte in audio]
    if not samples_8k:
        return b""

    samples_16k: list[int] = []
    for index, sample in enumerate(samples_8k):
        samples_16k.append(sample)
        next_sample = samples_8k[index + 1] if index + 1 < len(samples_8k) else sample
        samples_16k.append((sample + next_sample) // 2)
    return struct.pack("<" + "h" * len(samples_16k), *samples_16k)


def _pcm16_16k_to_mulaw_8k(audio: bytes) -> bytes:
    """Downsample PCM16 little-endian 16 kHz to Twilio μ-law 8 kHz."""
    if not audio:
        return b""
    sample_count = len(audio) // 2
    if sample_count == 0:
        return b""
    samples_16k = struct.unpack("<" + "h" * sample_count, audio[: sample_count * 2])
    # Take every other sample. This is intentionally simple and fast for
    # real-time telephony; the source is speech-band-limited by the agent.
    samples_8k = samples_16k[::2]
    return bytes(_pcm16_to_ulaw_byte(sample) for sample in samples_8k)


class TwilioAudioInterface(AudioInterface):
    def __init__(self, websocket: WebSocket) -> None:
        self.websocket = websocket
        self.input_callback = None
        self.stream_sid: str | None = None
        self.loop = asyncio.get_event_loop()

    def start(self, input_callback) -> None:
        self.input_callback = input_callback

    def stop(self) -> None:
        self.input_callback = None
        self.stream_sid = None

    def output(self, audio: bytes) -> None:
        """Called from the SDK's background thread; must return immediately."""
        asyncio.run_coroutine_threadsafe(
            self._send_audio_to_twilio(audio), self.loop
        )

    def interrupt(self) -> None:
        """Caller barged in — tell Twilio to drop any buffered agent audio."""
        asyncio.run_coroutine_threadsafe(
            self._send_clear_to_twilio(), self.loop
        )

    async def _send_audio_to_twilio(self, audio: bytes) -> None:
        if not self.stream_sid:
            return
        payload = base64.b64encode(_pcm16_16k_to_mulaw_8k(audio)).decode("utf-8")
        message = {
            "event": "media",
            "streamSid": self.stream_sid,
            "media": {"payload": payload},
        }
        try:
            if self.websocket.application_state == WebSocketState.CONNECTED:
                await self.websocket.send_text(json.dumps(message))
        except (WebSocketDisconnect, RuntimeError):
            pass

    async def _send_clear_to_twilio(self) -> None:
        if not self.stream_sid:
            return
        message = {"event": "clear", "streamSid": self.stream_sid}
        try:
            if self.websocket.application_state == WebSocketState.CONNECTED:
                await self.websocket.send_text(json.dumps(message))
        except (WebSocketDisconnect, RuntimeError):
            pass

    async def handle_twilio_message(self, data: dict) -> None:
        event = data.get("event")
        if event == "start":
            self.stream_sid = data["start"]["streamSid"]
        elif event == "media" and self.input_callback:
            audio_data = _mulaw_8k_to_pcm16_16k(
                base64.b64decode(data["media"]["payload"])
            )
            self.input_callback(audio_data)
