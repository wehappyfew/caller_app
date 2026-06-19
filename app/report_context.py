"""Per-call parking report details passed from run_calls.py into the live agent."""

from __future__ import annotations

from dataclasses import dataclass

from app.config import Settings

_pending_by_phone: dict[str, CallReportDetails] = {}

REPORT_FIELD_LABELS: dict[str, str] = {
    "location": "address (REPORT_LOCATION / --location)",
    "plate": "license plate (REPORT_PLATE / --plate)",
    "car_color": "car color (REPORT_CAR_COLOR / --color)",
    "car_brand": "car brand (REPORT_CAR_BRAND / --brand)",
}


def normalize_phone(phone: str) -> str:
    return phone.replace(" ", "")


@dataclass(frozen=True)
class CallReportDetails:
    location: str
    plate: str
    car_color: str
    car_brand: str

    def missing_fields(self) -> list[str]:
        missing: list[str] = []
        if not self.location.strip():
            missing.append("location")
        if not self.plate.strip():
            missing.append("plate")
        if not self.car_color.strip():
            missing.append("car_color")
        if not self.car_brand.strip():
            missing.append("car_brand")
        return missing

    def format_missing_message(self) -> str:
        labels = [REPORT_FIELD_LABELS[field] for field in self.missing_fields()]
        return "Missing required report details: " + ", ".join(labels)

    @classmethod
    def from_settings(cls, settings: Settings) -> CallReportDetails:
        return cls(
            location=settings.report_location,
            plate=settings.report_plate,
            car_color=settings.report_car_color,
            car_brand=settings.report_car_brand,
        )

    def as_dynamic_variables(self) -> dict[str, str]:
        return {
            "report_location": self.location,
            "report_plate": self.plate,
            "report_car_color": self.car_color,
            "report_car_brand": self.car_brand,
        }

    def as_stream_parameters(self) -> dict[str, str]:
        return self.as_dynamic_variables()


def stash_report_for_phone(phone: str, report: CallReportDetails) -> None:
    _pending_by_phone[normalize_phone(phone)] = report


def pop_report_for_phone(phone: str, settings: Settings) -> CallReportDetails:
    return _pending_by_phone.pop(normalize_phone(phone), CallReportDetails.from_settings(settings))


def report_from_stream_params(
    params: dict[str, str], settings: Settings
) -> CallReportDetails:
    """Build report details from Twilio stream custom parameters."""
    defaults = CallReportDetails.from_settings(settings)
    return CallReportDetails(
        location=(params.get("report_location") or defaults.location).strip(),
        plate=(params.get("report_plate") or defaults.plate).strip(),
        car_color=(params.get("report_car_color") or defaults.car_color).strip(),
        car_brand=(params.get("report_car_brand") or defaults.car_brand).strip(),
    )
