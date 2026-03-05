# UA Library Room Booker

Natural-language room booking automation for University of Arizona library rooms.

The project now supports:
- Local GUI and CLI runs.
- Telegram-triggered booking runs (good for VM deployment).
- A notifier seam for future Signal integration.

## Quick Start (Local)

1. Install Python 3.11+ and Google Chrome.
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Run GUI:
   ```bash
   python main.py
   ```
4. Run CLI:
   ```bash
   python main.py --cli
   ```

## Telegram Bot Mode

1. Copy `.env.example` to `.env`.
2. Fill in:
   - `TELEGRAM_BOT_TOKEN`
   - `TELEGRAM_ALLOWED_CHAT_IDS` (comma-separated numeric IDs)
3. Start bot:
   ```bash
   python main.py --telegram
   ```
4. In Telegram:
   - `/start`
   - `/book room for 4 people on Tuesday around 4pm`
   - `/status`

## Free VM Recommendation (Best Reliability)

For SSO-heavy sites, strict headless mode can be fragile. Prefer:
- Chrome in regular (headed) mode
- Running inside virtual display (`Xvfb`)
- Persistent Chrome profile for login session reuse

Recommended `.env` values:
- `BROWSER_HEADLESS=false`
- `BROWSER_INTERACTIVE_MODE=false`
- `BROWSER_KEEP_OPEN=false`
- `BROWSER_CLOSE_EXISTING=false`

Linux VM setup example:
```bash
sudo apt-get update
sudo apt-get install -y xvfb chromium-browser
xvfb-run -a python main.py --telegram
```

Initial bootstrap:
1. Start once in interactive mode (or attach VNC/desktop).
2. Complete university login manually.
3. Keep same profile directory for future unattended runs.

## Signal Integration Status

Signal is not enabled by default yet. A notifier interface and Signal stub are included so `signal-cli` can be added later without changing booking logic.

## Notes and Limitations

- Booking success is inferred from submit flow and page behavior; manual verification is still recommended.
- University login/session expiry can require periodic re-authentication.
- Website selector changes can break automation until selectors are updated.

## Main Files

- `main.py` - Entrypoint (`GUI`, `CLI`, or `--telegram`)
- `parser.py` - Natural language parser
- `browser.py` - Selenium booking automation
- `booking_service.py` - Reusable orchestration and result model
- `telegram_bot.py` - Telegram command handlers
- `config.py` - Environment-based runtime config
- `notifiers/base.py` - Notification interface
- `notifiers/signal_stub.py` - Placeholder for future Signal integration
