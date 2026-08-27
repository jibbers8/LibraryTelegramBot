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
   - Optional password gate:
     - `TELEGRAM_COMMAND_PASSWORD`
     - `TELEGRAM_UNLOCK_MINUTES` (default `60`)
3. Start bot:
   ```bash
   python main.py --telegram
   ```
4. In Telegram:
   - `/start`
   - `/unlock your-password` (if password gate enabled)
   - `/book room for 4 people on Tuesday around 4pm`
   - `/status`

## Room Continuation Preference

After a successful booking, the bot records the date, time, and room in
`state/recent_bookings.json`. On a later request for the same day that starts
at or after a prior booking ends, the room selector treats it as a natural
continuation:
- Try the exact same room first.
- If unavailable, try nearby rooms with the same room prefix and floor, within
  5 room numbers. For example, after `B539`, prefer `B538` or `B540` before
  unrelated qualifying rooms.
- If no same or nearby room is available, fall back to the normal preference
  for rooms with windows/natural light, then the first qualifying room.

The `state/` directory is intentionally ignored by git because it contains
runtime state such as approved Telegram chats and recent booking history.

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

## Deployed Google VM Operations

The live Telegram bot is not using Chrome on the local Windows machine. It runs
on a Google Compute Engine VM and uses a Chrome profile stored on that VM.

Known deployment details:
- Google Cloud project: `roombookertelegram`
- Compute Engine VM: `instance-20260305-025624`
- Zone: `us-west1-b`
- Linux user that runs the bot: `yakachakalaka`
- Repo path on VM: `/home/yakachakalaka/LibraryTelegramBot`
- systemd service: `library-booker-bot.service`
- Bot command: `python3 main.py --telegram`
- Display server: `Xvfb :99`
- Chrome profile used for UA/LibCal login:
  `/home/yakachakalaka/.config/UALibraryBooker`
- Chrome cache:
  `/home/yakachakalaka/.cache/UALibraryBooker`

Useful inspection commands from Windows:
```powershell
gcloud compute instances list --project roombookertelegram
gcloud compute ssh instance-20260305-025624 --zone us-west1-b --project roombookertelegram
```

Useful inspection commands on the VM:
```bash
sudo systemctl status library-booker-bot.service --no-pager -l
sudo journalctl -u library-booker-bot.service -n 120 --no-pager -o short-iso
sudo -u yakachakalaka bash -lc 'cd /home/yakachakalaka/LibraryTelegramBot && git status -sb && git log --oneline --max-count=5'
pgrep -af 'main.py --telegram|Xvfb|x11vnc|google-chrome|chromedriver'
```

### Refresh Expired UA Login

If bookings start but cannot complete because the UA/LibCal login expired,
refresh the login on the VM profile. Refreshing local Windows Chrome does not
help the deployed Telegram bot.

From Windows, pause the bot so it does not lock the Chrome profile:
```powershell
gcloud compute ssh instance-20260305-025624 --zone us-west1-b --project roombookertelegram --quiet --command 'bash -lc "sudo systemctl stop library-booker-bot.service; sudo pkill -u yakachakalaka -f chromedriver || true; sudo pkill -u yakachakalaka -f google-chrome || true; sudo pkill -u yakachakalaka -f chromium || true; sudo pkill -u yakachakalaka -f x11vnc || true"'
```

Start the VM desktop helpers and Chrome on the same profile the bot uses:
```powershell
gcloud compute ssh instance-20260305-025624 --zone us-west1-b --project roombookertelegram --quiet --command 'bash -lc "sudo -u yakachakalaka env DISPLAY=:99 nohup fluxbox >/tmp/library-booker-fluxbox.log 2>&1 & sudo -u yakachakalaka env DISPLAY=:99 nohup x11vnc -display :99 -localhost -rfbport 5900 -rfbauth /home/yakachakalaka/.vnc/passwd -forever -shared >/tmp/library-booker-x11vnc.log 2>&1 & sudo -u yakachakalaka env DISPLAY=:99 nohup google-chrome --user-data-dir=/home/yakachakalaka/.config/UALibraryBooker https://libcal.library.arizona.edu/ >/tmp/library-booker-chrome.log 2>&1 &"'
```

Open an SSH tunnel for TigerVNC:
```powershell
gcloud compute ssh instance-20260305-025624 --zone us-west1-b --project roombookertelegram --quiet --ssh-flag=-N --ssh-flag=-L --ssh-flag=5900:localhost:5900
```

Then connect TigerVNC to `localhost:5900`, complete the UA NetID/Duo login in
remote Chrome, and close Chrome.

If the VNC password is unknown, set a temporary one first. VNC auth only uses
the first 8 characters, so keep it 8 characters or shorter. Do not commit real
passwords or `.env` values to this repo:
```powershell
gcloud compute ssh instance-20260305-025624 --zone us-west1-b --project roombookertelegram --quiet --command 'bash -lc "sudo pkill -u yakachakalaka -f x11vnc || true; sudo -u yakachakalaka x11vnc -storepasswd TEMPVNC1 /home/yakachakalaka/.vnc/passwd; sudo chmod 600 /home/yakachakalaka/.vnc/passwd; sudo chown yakachakalaka:yakachakalaka /home/yakachakalaka/.vnc/passwd; sudo -u yakachakalaka env DISPLAY=:99 nohup x11vnc -display :99 -localhost -rfbport 5900 -rfbauth /home/yakachakalaka/.vnc/passwd -forever -shared >/tmp/library-booker-x11vnc.log 2>&1 &"'
```

After login, clean up the temporary desktop pieces and restart the bot:
```powershell
gcloud compute ssh instance-20260305-025624 --zone us-west1-b --project roombookertelegram --quiet --command 'bash -lc "sudo pkill -u yakachakalaka -f x11vnc || true; sudo pkill -u yakachakalaka -f google-chrome || true; sudo pkill -u yakachakalaka -f chromium || true; sudo pkill -u yakachakalaka -f fluxbox || true; sudo systemctl start library-booker-bot.service; sleep 5; sudo systemctl is-active library-booker-bot.service; sudo systemctl status library-booker-bot.service --no-pager -l | head -30"'
```

Successful reauthentication should update files such as:
```bash
/home/yakachakalaka/.config/UALibraryBooker/Default/Cookies
/home/yakachakalaka/.config/UALibraryBooker/Default/History
```

The Telegram `/update` command runs `git pull` inside
`/home/yakachakalaka/LibraryTelegramBot` and exits, relying on systemd to
restart the bot.

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
