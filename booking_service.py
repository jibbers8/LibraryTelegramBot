from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Callable

from browser import BookingAutomation
from parser import NaturalLanguageParser, BookingRequest
from notifiers.base import Notifier, NotificationPayload


@dataclass
class BookingResult:
    success: bool
    request_text: str
    request: BookingRequest
    started_at: datetime
    finished_at: datetime
    status_lines: list[str]
    skipped_dates: list[str] = field(default_factory=list)
    error: Optional[str] = None

    @property
    def duration_seconds(self) -> float:
        return (self.finished_at - self.started_at).total_seconds()

    def summary(self) -> str:
        if self.error:
            return f"Booking failed with error: {self.error}"
        return "Booking succeeded." if self.success else "Booking attempt finished, but success was not confirmed."

    def to_telegram_message(self) -> str:
        recent = "\n".join(f"- {line}" for line in self.status_lines[-8:]) if self.status_lines else "- No status messages"
        skipped = ""
        if self.skipped_dates:
            skipped_list = "\n".join(f"- {date_text}" for date_text in self.skipped_dates)
            skipped = f"\n\nSkipped dates:\n{skipped_list}"
        return (
            f"{'[SUCCESS]' if self.success else '[WARNING]'} {self.summary()}\n\n"
            f"Request:\n{self.request}\n\n"
            f"Duration: {self.duration_seconds:.1f}s\n"
            f"Started: {self.started_at.strftime('%Y-%m-%d %H:%M:%S')}\n\n"
            f"Recent status:\n{recent}"
            f"{skipped}"
        )


class BookingService:
    def __init__(self, parser: Optional[NaturalLanguageParser] = None, notifiers: Optional[list[Notifier]] = None):
        self.parser = parser or NaturalLanguageParser()
        self.notifiers = notifiers or []

    def run_from_text(
        self,
        request_text: str,
        *,
        headless: bool,
        interactive_mode: bool,
        keep_browser_open: bool,
        close_existing_browsers: bool,
        accept_similar_times: bool,
        progress_callback: Optional[Callable[[str], None]] = None,
    ) -> BookingResult:
        request = self.parser.parse(request_text)
        status_lines: list[str] = []
        started_at = datetime.now()

        def capture_status(message: str):
            status_lines.append(message)
            if progress_callback:
                try:
                    progress_callback(message)
                except Exception:
                    pass

        success = False
        error = None
        try:
            automation = BookingAutomation(
                headless=headless,
                status_callback=capture_status,
                accept_similar_times=accept_similar_times,
                interactive_mode=interactive_mode,
                keep_browser_open=keep_browser_open,
                close_existing_browsers=close_existing_browsers,
            )
            preview_params = automation._build_search_params(request)
            capture_status(
                "Computed search params -> "
                f"capacity={preview_params.get('capacity')} "
                f"start={preview_params.get('start', 'default')} "
                f"end={preview_params.get('end', 'default')} "
                f"date={preview_params.get('date', 'default')}"
            )
            success = automation.book_room(request)
        except Exception as exc:
            error = str(exc)

        finished_at = datetime.now()
        result = BookingResult(
            success=success,
            request_text=request_text,
            request=request,
            started_at=started_at,
            finished_at=finished_at,
            status_lines=status_lines,
            skipped_dates=getattr(automation, "recurring_failed_dates", []) if 'automation' in locals() else [],
            error=error,
        )
        self._notify(result)
        return result

    def _notify(self, result: BookingResult):
        payload = NotificationPayload(
            success=result.success,
            request_text=result.request_text,
            summary=result.summary(),
            started_at=result.started_at,
            finished_at=result.finished_at,
            status_lines=result.status_lines,
        )
        for notifier in self.notifiers:
            try:
                notifier.send(payload)
            except Exception:
                # Notifier failures should not break the booking workflow.
                continue
