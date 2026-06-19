import threading
from datetime import datetime
from pathlib import Path

from app.agent_profiles import format_agent_label
from app.report_context import CallReportDetails


class CallTranscriptLogger:
    """Append-only transcript log for one call: call_logs/call_<CallSid>.log"""

    def __init__(
        self,
        call_sid: str,
        *,
        contact_name: str,
        phone: str,
        language: str,
        logs_dir: Path,
        report: CallReportDetails | None = None,
        agent_id: str = "",
    ) -> None:
        self.call_sid = call_sid
        self._lock = threading.Lock()
        self._logs_dir = logs_dir
        self._logs_dir.mkdir(parents=True, exist_ok=True)
        self._path = self._logs_dir / f"call_{call_sid}.log"
        self._write_header(
            contact_name=contact_name,
            phone=phone,
            language=language,
            report=report,
            agent_id=agent_id,
        )

    @property
    def path(self) -> Path:
        return self._path

    def _write_header(
        self,
        *,
        contact_name: str,
        phone: str,
        language: str,
        report: CallReportDetails | None,
        agent_id: str,
    ) -> None:
        started = datetime.now().isoformat(timespec="seconds")
        lines = [
            f"call_sid={self.call_sid}",
            f"contact={contact_name}",
            f"phone={phone}",
            f"language={language}",
            f"started_at={started}",
        ]
        if agent_id:
            lines.append(f"agent_id={format_agent_label(agent_id)}")
        if report:
            lines.extend(
                [
                    f"report_location={report.location}",
                    f"report_plate={report.plate}",
                    f"report_car_color={report.car_color}",
                    f"report_car_brand={report.car_brand}",
                ]
            )
        lines.append("---")
        self._append_lines(lines)

    def log_agent(self, text: str) -> None:
        self._log_turn("Agent", text)

    def log_user(self, text: str) -> None:
        self._log_turn("User", text)

    def log_latency(self, ms: int) -> None:
        self._append_lines([f"[{self._timestamp()}] Latency: {ms}ms"])

    def log_note(self, message: str) -> None:
        self._append_lines([f"[{self._timestamp()}] {message}"])

    def log_cost_summary(self, table: str) -> None:
        self._append_lines(["---", "cost_summary", table, "---"])

    def close(self) -> None:
        self._append_lines([f"ended_at={datetime.now().isoformat(timespec='seconds')}"])

    def _log_turn(self, speaker: str, text: str) -> None:
        cleaned = (text or "").strip()
        if not cleaned:
            return
        self._append_lines([f"[{self._timestamp()}] {speaker}: {cleaned}"])

    def _append_lines(self, lines: list[str]) -> None:
        block = "\n".join(lines) + "\n"
        with self._lock:
            self._path.open("a", encoding="utf-8").write(block)

    @staticmethod
    def _timestamp() -> str:
        return datetime.now().strftime("%H:%M:%S")
