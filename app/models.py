from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class Contact:
    name: str
    phone: str
    birthday: str
    language: str = "el"
    timezone: str = "Europe/Athens"
    opt_in: bool = True
    opt_out: bool = False
    last_called_at: str = ""
    notes: str = ""


@dataclass
class CallSession:
    call_sid: str
    to_phone: str
    started_at: datetime
    language: str
    contact_name: str
    notes: str
    turns: int = 0
    done: bool = False
    history: list[str] = field(default_factory=list)
