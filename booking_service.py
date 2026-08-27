import re
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
    child_results: list = field(default_factory=list)
    error: Optional[str] = None

    @property
    def duration_seconds(self) -> float:
        return (self.finished_at - self.started_at).total_seconds()

    def summary(self) -> str:
        if self.child_results:
            successful = sum(1 for result in self.child_results if result.success)
            total = len(self.child_results)
            return f"Completed {successful}/{total} booking requests."
        if self.error:
            return f"Booking failed with error: {self.error}"
        return "Booking succeeded." if self.success else "Booking attempt finished, but success was not confirmed."

    def to_telegram_message(self) -> str:
        if self.child_results:
            lines = [
                f"{'[SUCCESS]' if self.success else '[WARNING]'} {self.summary()}",
                "",
            ]
            for i, result in enumerate(self.child_results, 1):
                status = "[SUCCESS]" if result.success else "[WARNING]"
                lines.extend([
                    f"{i}. {status} {result.summary()}",
                    str(result.request),
                ])
                if result.skipped_dates:
                    lines.append("Skipped dates: " + ", ".join(result.skipped_dates))
                lines.append("")
            if self.status_lines:
                recent = "\n".join(f"- {line}" for line in self.status_lines[-10:])
                lines.extend(["Recent status:", recent])
            lines.append(f"Duration: {self.duration_seconds:.1f}s")
            lines.append(f"Started: {self.started_at.strftime('%Y-%m-%d %H:%M:%S')}")
            return "\n".join(lines).strip()

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
    def __init__(
        self,
        parser: Optional[NaturalLanguageParser] = None,
        notifiers: Optional[list[Notifier]] = None,
        automation_factory: Callable[..., BookingAutomation] = BookingAutomation,
    ):
        self.parser = parser or NaturalLanguageParser()
        self.notifiers = notifiers or []
        self.automation_factory = automation_factory

    def split_compound_request(self, request_text: str) -> list[str]:
        parts = [part.strip() for part in re.split(r"\s+\bAND\b\s+", request_text) if part.strip()]
        if len(parts) > 1:
            return parts
        return [
            part.strip()
            for part in re.split(
                r"\s+\band\s+(?=(?:book|reserve|get|grab)\b)",
                request_text,
                flags=re.IGNORECASE,
            )
            if part.strip()
        ]

    def _inherit_missing_context(self, current: BookingRequest, previous: Optional[BookingRequest]):
        if previous is None:
            return
        if current.capacity is None:
            current.capacity = previous.capacity
        if current.room_type is None:
            current.room_type = previous.room_type
        if current.floor is None:
            current.floor = previous.floor
        if current.duration_hours == 1 and previous.duration_hours > 1:
            current.duration_hours = previous.duration_hours

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
        request_parts = self.split_compound_request(request_text)
        if len(request_parts) > 1:
            return self._run_compound_from_text(
                request_text,
                request_parts,
                headless=headless,
                interactive_mode=interactive_mode,
                keep_browser_open=keep_browser_open,
                close_existing_browsers=close_existing_browsers,
                accept_similar_times=accept_similar_times,
                progress_callback=progress_callback,
            )

        return self._run_single_from_text(
            request_text,
            headless=headless,
            interactive_mode=interactive_mode,
            keep_browser_open=keep_browser_open,
            close_existing_browsers=close_existing_browsers,
            accept_similar_times=accept_similar_times,
            progress_callback=progress_callback,
            notify=True,
        )

    def _run_single_from_text(
        self,
        request_text: str,
        *,
        headless: bool,
        interactive_mode: bool,
        keep_browser_open: bool,
        close_existing_browsers: bool,
        accept_similar_times: bool,
        progress_callback: Optional[Callable[[str], None]] = None,
        request_override: Optional[BookingRequest] = None,
        notify: bool = False,
    ) -> BookingResult:
        request = request_override or self.parser.parse(request_text)
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
            automation = self.automation_factory(
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
        if notify:
            self._notify(result)
        return result

    def _run_compound_from_text(
        self,
        original_request_text: str,
        request_parts: list[str],
        *,
        headless: bool,
        interactive_mode: bool,
        keep_browser_open: bool,
        close_existing_browsers: bool,
        accept_similar_times: bool,
        progress_callback: Optional[Callable[[str], None]] = None,
    ) -> BookingResult:
        started_at = datetime.now()
        status_lines: list[str] = [f"Split compound request into {len(request_parts)} booking requests."]
        child_results: list[BookingResult] = []
        previous_request = None

        def capture_status(message: str):
            status_lines.append(message)
            if progress_callback:
                try:
                    progress_callback(message)
                except Exception:
                    pass

        for i, part in enumerate(request_parts, 1):
            request = self.parser.parse(part)
            self._inherit_missing_context(request, previous_request)
            capture_status(f"Starting booking request {i}/{len(request_parts)}.")
            result = self._run_single_from_text(
                part,
                headless=headless,
                interactive_mode=interactive_mode,
                keep_browser_open=keep_browser_open,
                close_existing_browsers=close_existing_browsers,
                accept_similar_times=accept_similar_times,
                progress_callback=lambda message, index=i: capture_status(f"[{index}/{len(request_parts)}] {message}"),
                request_override=request,
                notify=False,
            )
            child_results.append(result)
            previous_request = request

        finished_at = datetime.now()
        aggregate_request = child_results[0].request if child_results else self.parser.parse(original_request_text)
        result = BookingResult(
            success=bool(child_results) and all(child.success for child in child_results),
            request_text=original_request_text,
            request=aggregate_request,
            started_at=started_at,
            finished_at=finished_at,
            status_lines=status_lines,
            skipped_dates=[date for child in child_results for date in child.skipped_dates],
            child_results=child_results,
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
