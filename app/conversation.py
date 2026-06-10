from datetime import datetime

from app.config import Settings
from app.models import CallSession


def initial_message(name: str, language: str) -> str:
    if language.lower().startswith("el"):
        return (
            f"Χρόνια πολλά {name}! Είμαι ένα αυτόματο τηλεφώνημα γενεθλίων. "
            "Ελπίζω να έχεις μια υπέροχη μέρα. Πώς είσαι σήμερα;"
        )
    return (
        f"Happy birthday {name}! This is your automated birthday caller. "
        "I hope you have a wonderful day. How are you today?"
    )


def next_response(
    session: CallSession,
    speech_result: str,
    confidence: float,
    settings: Settings,
) -> tuple[str, bool]:
    elapsed = (datetime.now() - session.started_at).total_seconds()
    if session.turns >= settings.max_turns or elapsed >= settings.call_timeout_seconds:
        return closing_message(session.language), True

    if confidence < 0.3:
        if session.language.lower().startswith("el"):
            return "Συγγνώμη, δεν σε άκουσα καθαρά. Να σου ευχηθώ ξανά χρόνια πολλά!", True
        return "Sorry, I could not hear you clearly. Happy birthday again!", True

    text = (speech_result or "").strip().lower()
    if any(token in text for token in {"stop", "opt out", "μη", "σταμάτα", "όχι κλήσεις"}):
        if session.language.lower().startswith("el"):
            return "Κατανοητό, δεν θα ξανακαλέσουμε. Χρόνια πολλά και καλή συνέχεια.", True
        return "Understood, we will not call again. Happy birthday and take care.", True

    if session.language.lower().startswith("el"):
        return "Τέλεια! Χαίρομαι που σε άκουσα. Να περάσεις φανταστικά σήμερα.", True
    return "Great to hear your voice. Have an amazing day and celebrate well.", True


def closing_message(language: str) -> str:
    if language.lower().startswith("el"):
        return "Χρόνια πολλά ξανά! Καλή συνέχεια."
    return "Happy birthday again. Have a great day."
