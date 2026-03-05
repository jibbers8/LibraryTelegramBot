import asyncio
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

    def _is_authorized(self, chat_id: int) -> bool:
        allowed = self.config.telegram_allowed_chat_ids
        if not allowed:
            return True
        return chat_id in allowed

    async def _require_auth(self, update: Update) -> bool:
        if update.effective_chat is None:
            return False
        if self._is_authorized(update.effective_chat.id):
            return True
        await update.message.reply_text("This chat is not authorized to run bookings.")
        return False

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await self._require_auth(update):
            return
        await update.message.reply_text(
            "Library booking bot is online.\n\n"
            "Use:\n"
            "/book <request text>\n"
            "/status"
        )

    async def help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await self._require_auth(update):
            return
        await update.message.reply_text(
            "Examples:\n"
            "/book room for 4 people tomorrow at 4pm\n"
            "/book quiet study room on friday afternoon"
        )

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

        try:
            result = await asyncio.to_thread(
                self.service.run_from_text,
                request_text,
                headless=self.config.browser_headless,
                interactive_mode=self.config.browser_interactive_mode,
                keep_browser_open=self.config.browser_keep_open,
                close_existing_browsers=self.config.browser_close_existing,
                accept_similar_times=self.config.accept_similar_times,
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
        application.add_handler(CommandHandler("status", self.status))
        application.add_handler(CommandHandler("book", self.book))
        return application


def run_telegram_bot(config: AppConfig):
    bot = TelegramBookingBot(config)
    app = bot.build_application()
    app.run_polling(poll_interval=config.telegram_poll_interval)
