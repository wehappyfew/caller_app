from app.config import get_settings
from app.csv_store import birthdays_for_today
from twilio.rest import Client


def main() -> None:
    settings = get_settings()
    contacts = birthdays_for_today(settings.csv_path, settings.timezone)
    if not contacts:
        print("No birthdays today.")
        return

    client = Client(settings.twilio_account_sid, settings.twilio_auth_token)
    webhook_url = f"{settings.public_base_url}/voice/inbound"

    print(f"Found {len(contacts)} birthday contact(s). Starting calls...")
    for contact in contacts:
        call = client.calls.create(
            to=contact.phone,
            from_=settings.twilio_from_number,
            url=webhook_url,
            method="POST",
            timeout=30,
        )
        print(f"Queued call for {contact.name} ({contact.phone}) - SID: {call.sid}")


if __name__ == "__main__":
    main()
