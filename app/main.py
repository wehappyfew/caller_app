from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, Form
from fastapi.responses import PlainTextResponse, Response
from fastapi.staticfiles import StaticFiles
from twilio.twiml.voice_response import Gather, VoiceResponse

from app.config import get_settings
from app.conversation import initial_message, next_response
from app.csv_store import contact_by_phone, load_contacts
from app.elevenlabs_tts import synthesize_to_file
from app.models import CallSession

settings = get_settings()
app = FastAPI(title="testapp_caller")

STATIC_DIR = Path("static")
GENERATED_DIR = STATIC_DIR / "generated"
GENERATED_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# In-memory sessions for MVP. Replace with Redis/DB for production.
SESSIONS: dict[str, CallSession] = {}


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


def _audio_url(filename: str) -> str:
    return f"{settings.public_base_url}/static/generated/{filename}"


def _response_with_gather(audio_file: str, language: str) -> str:
    vr = VoiceResponse()
    vr.play(_audio_url(audio_file))
    gather = Gather(
        input="speech",
        language="el-GR" if language.lower().startswith("el") else "en-US",
        speech_timeout="auto",
        action="/voice/process",
        method="POST",
    )
    vr.append(gather)
    vr.redirect("/voice/process")
    return str(vr)


@app.post("/voice/inbound")
def voice_inbound(call_sid: str = Form(alias="CallSid"), to_number: str = Form(alias="To")) -> Response:
    contacts = load_contacts(settings.csv_path)
    contact = contact_by_phone(contacts, to_number)
    name = contact.name if contact else "my friend"
    language = contact.language if contact else "en"
    notes = contact.notes if contact else ""

    SESSIONS[call_sid] = CallSession(
        call_sid=call_sid,
        to_phone=to_number,
        started_at=datetime.now(),
        language=language,
        contact_name=name,
        notes=notes,
    )

    msg = initial_message(name=name, language=language)
    audio_name = synthesize_to_file(
        settings=settings,
        text=msg,
        language=language,
        output_dir=GENERATED_DIR,
        filename_prefix=f"{call_sid}-greet",
    )
    twiml = _response_with_gather(audio_file=audio_name, language=language)
    return Response(content=twiml, media_type="application/xml")


@app.post("/voice/process")
def voice_process(
    call_sid: str = Form(alias="CallSid"),
    speech_result: str = Form(default="", alias="SpeechResult"),
    confidence: str = Form(default="0", alias="Confidence"),
) -> Response:
    session = SESSIONS.get(call_sid)
    if not session:
        vr = VoiceResponse()
        vr.say("Session not found. Goodbye.")
        vr.hangup()
        return Response(content=str(vr), media_type="application/xml")

    session.turns += 1
    conf_value = float(confidence) if confidence else 0.0
    reply_text, should_end = next_response(
        session=session,
        speech_result=speech_result,
        confidence=conf_value,
        settings=settings,
    )
    audio_name = synthesize_to_file(
        settings=settings,
        text=reply_text,
        language=session.language,
        output_dir=GENERATED_DIR,
        filename_prefix=f"{call_sid}-turn{session.turns}",
    )

    vr = VoiceResponse()
    vr.play(_audio_url(audio_name))
    if should_end:
        vr.hangup()
        session.done = True
    else:
        gather = Gather(
            input="speech",
            language="el-GR" if session.language.lower().startswith("el") else "en-US",
            speech_timeout="auto",
            action="/voice/process",
            method="POST",
        )
        vr.append(gather)
    return Response(content=str(vr), media_type="application/xml")


@app.get("/debug/sessions")
def debug_sessions() -> dict[str, dict]:
    return {
        sid: {
            "to_phone": s.to_phone,
            "contact_name": s.contact_name,
            "turns": s.turns,
            "done": s.done,
        }
        for sid, s in SESSIONS.items()
    }


@app.get("/")
def root() -> PlainTextResponse:
    return PlainTextResponse("testapp_caller running")
