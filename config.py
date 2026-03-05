import os
from dataclasses import dataclass


def _parse_bool(value: str, default: bool) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def _parse_int_list(value: str) -> list[int]:
    if not value:
        return []
    result = []
    for part in value.split(","):
        cleaned = part.strip()
        if cleaned:
            result.append(int(cleaned))
    return result


@dataclass
class AppConfig:
    telegram_bot_token: str
    telegram_allowed_chat_ids: list[int]
    telegram_poll_interval: float
    browser_headless: bool
    browser_interactive_mode: bool
    browser_keep_open: bool
    browser_close_existing: bool
    accept_similar_times: bool

    @classmethod
    def from_env(cls) -> "AppConfig":
        return cls(
            telegram_bot_token=os.getenv("TELEGRAM_BOT_TOKEN", "").strip(),
            telegram_allowed_chat_ids=_parse_int_list(os.getenv("TELEGRAM_ALLOWED_CHAT_IDS", "")),
            telegram_poll_interval=float(os.getenv("TELEGRAM_POLL_INTERVAL", "1.0")),
            browser_headless=_parse_bool(os.getenv("BROWSER_HEADLESS"), False),
            browser_interactive_mode=_parse_bool(os.getenv("BROWSER_INTERACTIVE_MODE"), False),
            browser_keep_open=_parse_bool(os.getenv("BROWSER_KEEP_OPEN"), False),
            browser_close_existing=_parse_bool(os.getenv("BROWSER_CLOSE_EXISTING"), False),
            accept_similar_times=_parse_bool(os.getenv("ACCEPT_SIMILAR_TIMES"), True),
        )
