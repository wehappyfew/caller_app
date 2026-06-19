import json
import logging
import traceback
from datetime import datetime
from pathlib import Path

from contextlib import asynccontextmanager

from elevenlabs import ElevenLabs
from elevenlabs.conversational_ai.conversation import Conversation
from fastapi import FastAPI, Form, Request, WebSocket
from fastapi.responses import PlainTextResponse, Response
from starlette.websockets import WebSocketDisconnect
from twilio.twiml.voice_response import Connect, VoiceResponse

from app.call_costs import build_call_cost_summary, log_call_cost_summary
from app.agent_config import build_conversation_init, sync_agent_from_settings
from app.agent_profiles import format_agent_label
from app.agent_context import pop_agent_for_phone
from app.call_log import CallTranscriptLogger
from app.config import get_settings
from app.csv_store import contact_by_phone, load_contacts
from app.models import CallSession
from app.report_context import pop_report_for_phone, report_from_stream_params
from app.twilio_audio_interface import TwilioAudioInterface

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("caller_app")

settings = get_settings()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    try:
        sync_agent_from_settings(settings)
    except Exception:
        logger.exception("Failed to sync ElevenLabs agent on startup")
    yield


app = FastAPI(title="caller_app", lifespan=lifespan)

SESSIONS: dict[str, CallSession] = {}
CALL_COST_SUMMARIES: dict[str, str] = {}


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


def _ws_url_for(request: Request) -> str:
    """Build the wss:// URL Twilio will dial for the media stream."""
    base = settings.public_base_url.rstrip("/")
    if base.startswith("https://"):
        return base.replace("https://", "wss://", 1) + "/media-stream"
    if base.startswith("http://"):
        return base.replace("http://", "ws://", 1) + "/media-stream"
    host = request.url.hostname or ""
    return f"wss://{host}/media-stream"


@app.post("/voice/inbound")
def voice_inbound(
    request: Request,
    call_sid: str = Form(alias="CallSid"),
    to_number: str = Form(alias="To"),
) -> Response:
    contacts = load_contacts(settings.csv_path)
    contact = contact_by_phone(contacts, to_number)
    name = contact.name if contact else "friend"
    language = contact.language if contact else "en"
    notes = contact.notes if contact else ""

    report = pop_report_for_phone(to_number, settings)
    if report.missing_fields():
        logger.error(
            "Inbound call %s rejected: %s",
            call_sid,
            report.format_missing_message(),
        )
        vr = VoiceResponse()
        vr.hangup()
        return Response(content=str(vr), media_type="application/xml")

    agent_id = pop_agent_for_phone(to_number, settings)

    SESSIONS[call_sid] = CallSession(
        call_sid=call_sid,
        to_phone=to_number,
        started_at=datetime.now(),
        language=language,
        contact_name=name,
        notes=notes,
    )

    vr = VoiceResponse()
    connect = Connect()
    stream = connect.stream(url=_ws_url_for(request))
    stream.parameter(name="contact_name", value=name)
    stream.parameter(name="language", value=language)
    stream.parameter(name="notes", value=notes)
    for key, value in report.as_stream_parameters().items():
        stream.parameter(name=key, value=value)
    stream.parameter(name="agent_id", value=agent_id)
    vr.append(connect)
    logger.info(
        "Inbound call %s -> %s (%s, %s) plate=%s agent=%s",
        call_sid,
        name,
        to_number,
        language,
        report.plate,
        format_agent_label(agent_id),
    )
    return Response(content=str(vr), media_type="application/xml")


@app.websocket("/media-stream")
async def media_stream(websocket: WebSocket) -> None:
    await websocket.accept()
    logger.info("Twilio media stream connected")

    audio_interface = TwilioAudioInterface(websocket)
    contact_name = "friend"
    language = "en"
    notes = ""
    report = None
    agent_id = ""
    call_sid: str | None = None
    transcript: CallTranscriptLogger | None = None

    try:
        async for raw in websocket.iter_text():
            data = json.loads(raw) if raw else {}
            event = data.get("event")
            if event == "start":
                start = data.get("start", {})
                call_sid = start.get("callSid")
                params = start.get("customParameters", {}) or {}
                contact_name = params.get("contact_name", contact_name)
                language = params.get("language", language)
                notes = params.get("notes", notes)
                report = report_from_stream_params(params, settings)
                if report.missing_fields():
                    logger.error(
                        "Media stream rejected call_sid=%s: %s",
                        call_sid,
                        report.format_missing_message(),
                    )
                    return
                agent_id = (params.get("agent_id") or "").strip()
                if not agent_id:
                    session = SESSIONS.get(call_sid or "")
                    agent_id = pop_agent_for_phone(
                        session.to_phone if session else "",
                        settings,
                    )
                await audio_interface.handle_twilio_message(data)
                logger.info(
                    "Stream start call_sid=%s contact=%s language=%s plate=%s agent=%s",
                    call_sid,
                    contact_name,
                    language,
                    report.plate,
                    format_agent_label(agent_id),
                )
                session = SESSIONS.get(call_sid or "")
                transcript = CallTranscriptLogger(
                    call_sid or "unknown",
                    contact_name=contact_name,
                    phone=session.to_phone if session else "",
                    language=language,
                    logs_dir=Path(settings.call_logs_dir),
                    report=report,
                    agent_id=agent_id,
                )
                logger.info("Transcript log: %s", transcript.path)
                break
            if event in {"connected", "mark"}:
                continue
            if event == "stop":
                logger.info("Stream stopped before start; closing")
                return

        client = ElevenLabs(api_key=settings.elevenlabs_api_key)
        config = build_conversation_init(
            settings,
            contact_name=contact_name,
            language=language,
            notes=notes,
            report=report,
        )

        def on_agent(text: str) -> None:
            logger.info("[Agent] %s", text)
            if transcript:
                transcript.log_agent(text)

        def on_user(text: str) -> None:
            logger.info("[User]  %s", text)
            if transcript:
                transcript.log_user(text)

        def on_latency(ms: int) -> None:
            logger.info("[Latency] %dms", ms)
            if transcript:
                transcript.log_latency(ms)

        conversation = Conversation(
            client=client,
            agent_id=agent_id,
            requires_auth=True,
            audio_interface=audio_interface,
            config=config,
            callback_agent_response=on_agent,
            callback_user_transcript=on_user,
            callback_latency_measurement=on_latency,
        )
        conversation.start_session()
        logger.info("ElevenLabs conversation started for call %s", call_sid)

        async for raw in websocket.iter_text():
            if not raw:
                continue
            data = json.loads(raw)
            if data.get("event") == "stop":
                logger.info("Twilio stream stop event received")
                break
            await audio_interface.handle_twilio_message(data)

    except WebSocketDisconnect:
        logger.info("Twilio websocket disconnected")
        if transcript:
            transcript.log_note("Twilio websocket disconnected")
    except Exception:
        logger.error("Media stream error:\n%s", traceback.format_exc())
        if transcript:
            transcript.log_note(f"Error: {traceback.format_exc()}")
    finally:
        conversation_id: str | None = None
        try:
            conversation  # type: ignore[name-defined]
            conversation.end_session()
            conversation_id = conversation.wait_for_session_end()
            logger.info("ElevenLabs conversation ended id=%s", conversation_id)
        except NameError:
            pass
        except Exception:
            logger.error("Error ending conversation:\n%s", traceback.format_exc())

        if call_sid:
            try:
                summary = build_call_cost_summary(
                    settings,
                    call_sid=call_sid,
                    conversation_id=conversation_id,
                )
                log_call_cost_summary(summary)
                CALL_COST_SUMMARIES[call_sid] = summary.as_table()
                if transcript:
                    transcript.log_cost_summary(summary.as_table())
            except Exception:
                logger.exception("Failed to build call cost summary for %s", call_sid)

        if transcript:
            transcript.close()
        if call_sid and call_sid in SESSIONS:
            SESSIONS[call_sid].done = True


@app.get("/debug/call-summary/{call_sid}")
def debug_call_summary(call_sid: str) -> PlainTextResponse:
    summary = CALL_COST_SUMMARIES.get(call_sid)
    if not summary:
        return PlainTextResponse("", status_code=404)
    return PlainTextResponse(summary)


@app.get("/debug/sessions")
def debug_sessions() -> dict[str, dict]:
    return {
        sid: {
            "to_phone": s.to_phone,
            "contact_name": s.contact_name,
            "language": s.language,
            "turns": s.turns,
            "done": s.done,
        }
        for sid, s in SESSIONS.items()
    }


@app.get("/")
def root() -> PlainTextResponse:
    return PlainTextResponse("caller_app running")
