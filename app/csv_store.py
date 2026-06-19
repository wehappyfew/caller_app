import csv
from pathlib import Path

from app.models import Contact


class ContactSelectionError(Exception):
    """Raised when no contact can be selected for an outbound call."""


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
                    language=(row.get("language") or "el").strip() or "el",
                    timezone=(row.get("timezone") or "Europe/Athens").strip() or "Europe/Athens",
                    last_called_at=(row.get("last_called_at") or "").strip(),
                    notes=(row.get("notes") or "").strip(),
                )
            )
    return contacts


def contact_by_name(contacts: list[Contact], name: str) -> Contact | None:
    target = name.strip().lower()
    for contact in contacts:
        if contact.name.strip().lower() == target:
            return contact
    return None


def resolve_contact_to_call(csv_path: str, contact_name: str | None) -> Contact:
    """Pick a contact by name from the CSV."""
    if not contact_name or not contact_name.strip():
        raise ContactSelectionError(
            "No contact specified. Use --contact NAME or set CALL_CONTACT in .env."
        )

    contacts = load_contacts(csv_path)
    if not contacts:
        raise ContactSelectionError("CSV has no contacts.")

    match = contact_by_name(contacts, contact_name)
    if not match:
        available = ", ".join(c.name for c in contacts if c.name) or "(none)"
        raise ContactSelectionError(
            f"Contact '{contact_name.strip()}' not found. Available: {available}"
        )
    return match


def contact_by_phone(contacts: list[Contact], phone: str) -> Contact | None:
    normalized = phone.replace(" ", "")
    for contact in contacts:
        if contact.phone.replace(" ", "") == normalized:
            return contact
    return None
