import csv
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from app.models import Contact


def _parse_bool(value: str, default: bool) -> bool:
    if value is None or value == "":
        return default
    return value.strip().lower() in {"1", "true", "yes", "y"}


def load_contacts(csv_path: str) -> list[Contact]:
    path = Path(csv_path)
    if not path.exists():
        raise FileNotFoundError(f"CSV file not found: {csv_path}")

    contacts: list[Contact] = []
    with path.open("r", encoding="utf-8", newline="") as file_obj:
        reader = csv.DictReader(file_obj)
        for row in reader:
            contacts.append(
                Contact(
                    name=(row.get("name") or "").strip(),
                    phone=(row.get("phone") or "").strip(),
                    birthday=(row.get("birthday") or "").strip(),
                    language=(row.get("language") or "el").strip() or "el",
                    timezone=(row.get("timezone") or "Europe/Athens").strip() or "Europe/Athens",
                    opt_in=_parse_bool(row.get("opt_in"), True),
                    opt_out=_parse_bool(row.get("opt_out"), False),
                    last_called_at=(row.get("last_called_at") or "").strip(),
                    notes=(row.get("notes") or "").strip(),
                )
            )
    return contacts


def is_birthday_today(contact: Contact, default_timezone: str) -> bool:
    tz_name = contact.timezone or default_timezone
    now = datetime.now(ZoneInfo(tz_name))
    try:
        bday = datetime.fromisoformat(contact.birthday)
    except ValueError:
        return False
    return now.month == bday.month and now.day == bday.day


def contact_by_phone(contacts: list[Contact], phone: str) -> Contact | None:
    normalized = phone.replace(" ", "")
    for contact in contacts:
        if contact.phone.replace(" ", "") == normalized:
            return contact
    return None


def birthdays_for_today(csv_path: str, default_timezone: str) -> list[Contact]:
    contacts = load_contacts(csv_path)
    result: list[Contact] = []
    for contact in contacts:
        if not contact.opt_in or contact.opt_out:
            continue
        if is_birthday_today(contact, default_timezone):
            result.append(contact)
    return result
