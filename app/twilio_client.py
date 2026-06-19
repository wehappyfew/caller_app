import time

from twilio.rest import Client

from app.config import Settings

CANCELABLE_CALL_STATUSES = frozenset({"queued", "ringing"})
ENDABLE_CALL_STATUSES = frozenset({"queued", "ringing", "in-progress"})
TERMINAL_CALL_STATUSES = frozenset(
    {"completed", "busy", "failed", "no-answer", "canceled"}
)


def get_twilio_client(settings: Settings) -> Client:
    if settings.twilio_api_key_sid:
        return Client(
            settings.twilio_api_key_sid,
            settings.twilio_auth_token,
            settings.twilio_account_sid,
        )
    return Client(settings.twilio_account_sid, settings.twilio_auth_token)


def ring_timeout_seconds(settings: Settings) -> int:
    """Twilio answer timeout from max rings (5–600 seconds per Twilio API)."""
    seconds = int(settings.call_max_rings * settings.call_ring_seconds)
    return max(5, min(600, seconds))


def stop_call(
    client: Client,
    call_sid: str,
    *,
    contact_name: str = "",
) -> bool:
    """Cancel ringing or hang up an active call. Returns True if Twilio was updated."""
    call = client.calls(call_sid).fetch()
    if call.status in TERMINAL_CALL_STATUSES:
        return False
    if call.status not in ENDABLE_CALL_STATUSES:
        return False

    label = contact_name or call_sid
    if call.status in CANCELABLE_CALL_STATUSES:
        client.calls(call_sid).update(status="canceled")
        print(f"Canceled call to {label}")
    else:
        client.calls(call_sid).update(status="completed")
        print(f"Ended call with {label}")
    return True


def watch_call_progress(
    client: Client,
    call_sid: str,
    contact_name: str,
    *,
    max_rings: int,
    ring_seconds: float,
    poll_seconds: float = 1.0,
    timeout_seconds: int = 600,
):
    """Poll Twilio call status; print pickup and cancel if still ringing after max rings."""
    ring_limit = max(5, int(max_rings * ring_seconds))
    deadline = time.time() + timeout_seconds
    last_status: str | None = None
    ringing_started: float | None = None
    answered_printed = False

    while time.time() < deadline:
        call = client.calls(call_sid).fetch()
        status = call.status

        if status != last_status:
            if status == "ringing":
                print(f"Ringing {contact_name}...")
                ringing_started = time.time()
            elif status == "in-progress" and not answered_printed:
                print(f"{contact_name} answered")
                answered_printed = True
            elif status == "no-answer":
                print(
                    f"No answer from {contact_name} "
                    f"(stopped after {max_rings} rings)"
                )
            last_status = status

        if status == "ringing" and ringing_started is not None:
            if time.time() - ringing_started >= ring_limit:
                if call.status in CANCELABLE_CALL_STATUSES:
                    client.calls(call_sid).update(status="canceled")
                    print(
                        f"No answer from {contact_name} "
                        f"(canceled after {max_rings} rings)"
                    )
                return client.calls(call_sid).fetch()

        if status in TERMINAL_CALL_STATUSES:
            return call

        time.sleep(poll_seconds)

    return client.calls(call_sid).fetch()
