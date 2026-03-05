from dataclasses import dataclass
from datetime import datetime


@dataclass
class NotificationPayload:
    success: bool
    request_text: str
    summary: str
    started_at: datetime
    finished_at: datetime
    status_lines: list[str]


class Notifier:
    def send(self, payload: NotificationPayload) -> None:
        raise NotImplementedError()
