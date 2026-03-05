import asyncio
import json
import os
import subprocess
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

from booking_service import BookingService, BookingResult
from config import AppConfig


class TelegramBookingBot:
    def __init__(self, config: AppConfig):
        self.config = config
        self.service = BookingService()
        self.last_result: Optional[BookingResult] = None
        self.unlocked_chats: dict[int, datetime] = {}
        self.repo_root = Path(__file__).resolve().parent
        self.state_dir = self.repo_root / "state"
        self.approved_chats_path = self.state_dir / "approved_chats.json"
        self.approved_chats = self._load_approved_chats()

    def _load_approved_chats(self) -> set[int]:
        try:
            if not self.approved_chats_path.exists():
                return set()
            data = json.loads(self.approved_chats_path.read_text(encoding="utf-8"))
            if not isinstance(data, list):
                return set()
            return {int(chat_id) for chat_id in data}
        except Exception:
            return set()

    def _save_approved_chats(self):
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.approved_chats_path.write_text(
            json.dumps(sorted(self.approved_chats), indent=2),
            encoding="utf-8",
        )

    def _is_authorized(self, chat_id: int) -> bool:
        if chat_id in self.approved_chats:
            return True
        allowed = self.config.telegram_allowed_chat_ids
        if not allowed:
            return True
        return chat_id in allowed

    def _is_password_unlocked(self, chat_id: int) -> bool:
        if chat_id in self.approved_chats:
            return True
        if not self.config.telegram_command_password:
            return True
        expires_at = self.unlocked_chats.get(chat_id)
        if not expires_at:
            return False
        if expires_at < datetime.now():
            self.unlocked_chats.pop(chat_id, None)
            return False
        return True

    async def _require_auth(self, update: Update) -> bool:
        if update.effective_chat is None:
            return False
        chat_id = update.effective_chat.id
        if not self._is_authorized(chat_id):
            await update.message.reply_text("This chat is not authorized to run bookings.")
            return False
        if self._is_password_unlocked(chat_id):
            return True
        await update.message.reply_text(
            "This bot is locked.\n"
            "Use /unlock <password> to enable commands in this chat."
        )
        return False

    async def unlock(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.effective_chat is None:
            return
        chat_id = update.effective_chat.id
        if not self._is_authorized(chat_id):
            await update.message.reply_text("This chat is not authorized to run bookings.")
            return
        if not self.config.telegram_command_password:
            await update.message.reply_text("Password lock is disabled for this bot.")
            return
        provided = " ".join(context.args).strip()
        if not provided:
            await update.message.reply_text("Usage: /unlock <password>")
            return
        if provided != self.config.telegram_command_password:
            await update.message.reply_text("Incorrect password.")
            return
        self.approved_chats.add(chat_id)
        self._save_approved_chats()
        self.unlocked_chats.pop(chat_id, None)
        await update.message.reply_text("Unlocked permanently for this chat.")

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.effective_chat is None:
            return
        if not self._is_authorized(update.effective_chat.id):
            await update.message.reply_text("This chat is not authorized to run bookings.")
            return
        await update.message.reply_text(
            "Library booking bot is online.\n\n"
            "Use:\n"
            "/unlock <password> (if password lock is enabled)\n"
            "/book <request text>\n"
            "/status\n"
            "/version\n"
            "/update\n"
            "/help"
        )

    async def help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await self._require_auth(update):
            return
        await update.message.reply_text(
            "How to use /book:\n"
            "- /book <natural-language request>\n\n"
            "Supported notation:\n"
            "- People: 'for 4 people', 'group of 6'\n"
            "- Date: 'today', 'tomorrow', 'this tuesday', 'next tuesday', 'March 14'\n"
            "- Recurring: 'next 4 tuesdays', 'every tuesday for 4 weeks'\n"
            "- Time range: 'from 8pm to 10pm', 'between 10am and 2pm', '8pm-10pm'\n"
            "- Single time: 'at 4pm', 'around 2:30pm', 'friday afternoon'\n"
            "- Room type: 'quiet', 'group', 'video conference', 'presentation'\n"
            "- Floor: 'on the 3rd floor'\n\n"
            "Examples:\n"
            "/book room for 4 people from 8pm to 10pm this tuesday\n"
            "/book quiet study room next 4 tuesdays from 6pm to 8pm\n"
            "/book group room for 6 students tomorrow at 4pm\n\n"
            "Notes:\n"
            "- Bot books only if exact requested time has availability.\n"
            "- For recurring requests, unavailable dates are skipped and listed in the result.\n\n"
            "Maintenance commands:\n"
            "- /version: show current git commit\n"
            "- /update: pull latest GitHub changes and restart bot\n\n"
            "Password behavior:\n"
            "- /unlock is permanent per chat once successful"
        )

    async def version(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await self._require_auth(update):
            return
        repo_root = Path(__file__).resolve().parent
        try:
            commit = subprocess.check_output(
                ["git", "rev-parse", "--short", "HEAD"],
                cwd=repo_root,
                text=True,
            ).strip()
            await update.message.reply_text(f"Current version: {commit}")
        except Exception as exc:
            await update.message.reply_text(f"Could not read version: {exc}")

    async def update(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await self._require_auth(update):
            return
        repo_root = Path(__file__).resolve().parent
        await update.message.reply_text("Checking for updates from GitHub...")
        try:
            pull_result = subprocess.run(
                ["git", "pull"],
                cwd=repo_root,
                text=True,
                capture_output=True,
                check=False,
            )
            output = (pull_result.stdout or "") + (pull_result.stderr or "")
            output = output.strip() or "(no output)"
            if pull_result.returncode != 0:
                await update.message.reply_text(f"Update failed:\n{output}")
                return
            if "Already up to date." in output:
                await update.message.reply_text("Already up to date.")
                return
            await update.message.reply_text(f"Update applied:\n{output}\n\nRestarting bot now...")
            await asyncio.sleep(1)
            os._exit(0)
        except Exception as exc:
            await update.message.reply_text(f"Update failed: {exc}")

    async def status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await self._require_auth(update):
            return
        if not self.last_result:
            await update.message.reply_text("No booking runs yet.")
            return
        await update.message.reply_text(self.last_result.to_telegram_message())

    async def book(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await self._require_auth(update):
            return

        request_text = " ".join(context.args).strip()
        if not request_text:
            await update.message.reply_text("Usage: /book <your natural-language request>")
            return

        await update.message.reply_text(
            "Booking started. This can take up to a few minutes. "
            "You will get a completion message."
        )

        progress_state = {"count": 0}
        loop = asyncio.get_running_loop()
        chat_id = update.effective_chat.id if update.effective_chat else None
        app = context.application

        def progress_callback(message: str):
            if not chat_id or not message:
                return
            progress_state["count"] += 1
            # Keep progress updates readable while still showing step-by-step execution.
            if progress_state["count"] <= 3 or progress_state["count"] % 2 == 0:
                future = asyncio.run_coroutine_threadsafe(
                    app.bot.send_message(chat_id=chat_id, text=f"Step {progress_state['count']}: {message}"),
                    loop,
                )
                try:
                    future.result(timeout=5)
                except Exception:
                    pass

        try:
            result = await asyncio.to_thread(
                self.service.run_from_text,
                request_text,
                headless=self.config.browser_headless,
                interactive_mode=self.config.browser_interactive_mode,
                keep_browser_open=self.config.browser_keep_open,
                close_existing_browsers=self.config.browser_close_existing,
                accept_similar_times=self.config.accept_similar_times,
                progress_callback=progress_callback,
            )
            self.last_result = result
            await update.message.reply_text(result.to_telegram_message())
        except Exception as exc:
            await update.message.reply_text(f"Booking failed: {exc}")

    def build_application(self) -> Application:
        if not self.config.telegram_bot_token:
            raise ValueError("TELEGRAM_BOT_TOKEN is missing.")

        application = Application.builder().token(self.config.telegram_bot_token).build()
        application.add_handler(CommandHandler("start", self.start))
        application.add_handler(CommandHandler("help", self.help))
        application.add_handler(CommandHandler("unlock", self.unlock))
        application.add_handler(CommandHandler("version", self.version))
        application.add_handler(CommandHandler("update", self.update))
        application.add_handler(CommandHandler("status", self.status))
        application.add_handler(CommandHandler("book", self.book))
        return application


def run_telegram_bot(config: AppConfig):
    bot = TelegramBookingBot(config)
    app = bot.build_application()
    app.run_polling(poll_interval=config.telegram_poll_interval)
