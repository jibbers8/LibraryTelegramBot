import time
import os
import subprocess
from datetime import datetime
from urllib.parse import urlencode
from typing import Optional, Callable
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from webdriver_manager.chrome import ChromeDriverManager

from parser import BookingRequest


class BookingAutomation:
    BASE_URL = "https://libcal.library.arizona.edu"

    CAPACITY_MAP = {"1": 2, "2": 5, "3": 12}
    ROOM_TYPE_MAP = {"quiet": "1393", "group": "1389", "video": "29391", "presentation": "29392"}
    TIME_RANGES = {
        "morning": ("08:00", "12:00"), "afternoon": ("12:00", "17:00"),
        "evening": ("17:00", "21:00"), "night": ("18:00", "23:00"),
        "noon": ("11:00", "13:00"), "midday": ("11:00", "14:00"), "lunch": ("11:00", "14:00"),
    }

    def _get_capacity_value(self, capacity):
        if not capacity:
            return "0"
        for val, max_cap in self.CAPACITY_MAP.items():
            if capacity <= max_cap:
                return val
        return "4"

    def _build_search_url(self, request, date_override=None) -> str:
        params = {"m": "t", "lid": "801", "gid": "1389", "zone": "0",
                  "capacity": self._get_capacity_value(request.capacity)}

        if request.room_type and request.room_type in self.ROOM_TYPE_MAP:
            params["gid"] = self.ROOM_TYPE_MAP[request.room_type]

        booking_date = date_override or request.date
        if booking_date:
            params["date"] = booking_date.strftime("%Y-%m-%d")

        if request.start_hour is not None and request.end_hour is not None:
            params["start"] = f"{request.start_hour:02d}:00"
            params["end"] = f"{request.end_hour:02d}:00"
        elif request.target_hour is not None:
            params["start"] = f"{max(0, request.target_hour - 1):02d}:00"
            params["end"] = f"{min(23, request.target_hour + 1):02d}:00"
        elif request.time_preference and request.time_preference in self.TIME_RANGES:
            params["start"], params["end"] = self.TIME_RANGES[request.time_preference]

        return f"{self.BASE_URL}/r/search?{urlencode(params)}"

    def __init__(
        self,
        headless: bool = False,
        status_callback: Optional[Callable[[str], None]] = None,
        accept_similar_times: bool = True,
        interactive_mode: bool = True,
        keep_browser_open: bool = True,
        close_existing_browsers: bool = True,
    ):
        self.driver: Optional[webdriver.Chrome] = None
        self.headless = headless
        self.status_callback = status_callback or print
        self.accept_similar_times = accept_similar_times
        self.interactive_mode = interactive_mode
        self.keep_browser_open = keep_browser_open
        self.close_existing_browsers = close_existing_browsers

    def _update_status(self, message: str):
        self.status_callback(message)

    def start_browser(self):
        self._update_status("Setting up Chrome...")
        if self.close_existing_browsers:
            self._update_status("Closing any existing Chrome instances...")
            try:
                subprocess.run(["taskkill", "/F", "/IM", "chrome.exe"], capture_output=True, timeout=10)
                subprocess.run(["taskkill", "/F", "/IM", "chromedriver.exe"], capture_output=True, timeout=5)
                time.sleep(3)
                subprocess.run(["taskkill", "/F", "/IM", "chrome.exe"], capture_output=True, timeout=5)
                time.sleep(2)
            except Exception:
                pass
        else:
            self._update_status("Keeping existing Chrome processes untouched.")

        base_profile_dir = os.environ.get("LOCALAPPDATA")
        if not base_profile_dir:
            base_profile_dir = os.path.join(os.path.expanduser("~"), ".config")
        app_profile_dir = os.path.join(base_profile_dir, "UALibraryBooker")
        options = Options()
        options.add_argument(f"--user-data-dir={app_profile_dir}")
        if self.headless:
            options.add_argument("--headless=new")

        for arg in ["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu", "--no-first-run",
                    "--no-default-browser-check", "--disable-blink-features=AutomationControlled",
                    "--start-maximized", "--disable-extensions", "--disable-popup-blocking"]:
            options.add_argument(arg)

        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option("useAutomationExtension", False)

        self._update_status("Starting Chrome...")

        try:
            service = Service(ChromeDriverManager().install())
            self.driver = webdriver.Chrome(service=service, options=options)
            try:
                self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            except Exception:
                pass
            self._update_status("Chrome started successfully!")
        except Exception as e:
            error_msg = str(e)
            self._update_status(f"Failed to start Chrome: {error_msg}")
            if "user data directory is already in use" in error_msg.lower():
                self._update_status("ERROR: Chrome profile is locked! Close ALL Chrome windows and try again.")
            raise

    def close_browser(self):
        if self.driver:
            try:
                self.driver.quit()
            except Exception:
                pass
            self.driver = None
            self._update_status("Disconnected from browser.")

    def _wait_for_user_confirmation(self, prompt: str):
        prompt_text = prompt or "Waiting for manual confirmation"
        if self.interactive_mode:
            input(prompt_text)
            return
        self._update_status(f"Non-interactive mode: {prompt_text} (skipped)")

    def _set_date(self, date: datetime):
        date_str_iso = date.strftime("%Y-%m-%d")
        self._update_status(f"Setting date to {date.strftime('%m/%d/%Y')}...")

        js_code = """
            var input = document.getElementById('s-lc-date');
            if (input) {
                input.value = arguments[0];
                input.dispatchEvent(new Event('input', { bubbles: true }));
                input.dispatchEvent(new Event('change', { bubbles: true }));
                return input.value;
            }
            return null;
        """
        result = self.driver.execute_script(js_code, date_str_iso)

        if result != date_str_iso:
            self._set_date_via_keyboard(date)

    def _set_date_via_keyboard(self, date: datetime):
        try:
            date_input = self.driver.find_element(By.ID, "s-lc-date")
            date_input.click()
            time.sleep(0.3)
            for _ in range(10):
                date_input.send_keys(Keys.ARROW_LEFT)
            for part in [date.strftime("%m"), date.strftime("%d"), date.strftime("%Y")]:
                date_input.send_keys(part)
                time.sleep(0.1)
        except Exception as e:
            self._update_status(f"Keyboard date entry failed: {e}")

    def find_available_rooms(self, request: BookingRequest) -> list[dict]:
        self._update_status("Searching for available rooms...")
        rooms = []

        try:
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, ".s-lc-suggestion-book-now"))
            )

            page_text = self.driver.page_source.lower()
            if "no results available" in page_text or "sorry" in page_text:
                if not self.accept_similar_times:
                    self._update_status("Exact time not available. Similar times disabled - skipping.")
                    return []
                self._update_status("Exact time not available. Booking similar-time room...")

            book_buttons = self.driver.find_elements(By.CSS_SELECTOR, ".s-lc-suggestion-book-now")
            self._update_status(f"Found {len(book_buttons)} available room(s)!")

            for btn in book_buttons:
                try:
                    room_container = btn.find_element(By.XPATH, "./ancestor::div[contains(@class, 's-lc-suggestion') or contains(@class, 'media')]")
                    try:
                        heading = room_container.find_element(By.CSS_SELECTOR, ".s-lc-suggestion-heading, .media-heading, h3, h4")
                        room_name = heading.text.strip()
                    except Exception:
                        room_name = "Unknown Room"
                    rooms.append({"name": room_name, "description": room_container.text.lower(), "button": btn})
                except Exception:
                    rooms.append({"name": "Available Room", "description": "", "button": btn})

        except TimeoutException:
            self._update_status("No rooms found or page structure changed.")

        return rooms

    def _select_preferred_room(self, rooms: list[dict]) -> dict:
        if not rooms:
            return None

        preferred = [r for r in rooms if any(kw in r.get("description", "") for kw in ["window", "natural light"])]
        if preferred:
            self._update_status(f"Found {len(preferred)} room(s) with windows/natural light!")
            return preferred[0]

        self._update_status("No rooms with windows found, using first available room.")
        return rooms[0]

    def _is_booking_confirmed(self) -> bool:
        current_url = (self.driver.current_url or "").lower()
        page_text = (self.driver.page_source or "").lower()
        return (
            "booking confirmed" in page_text
            or "booking confirmed" in current_url
            or "reservation confirmed" in page_text
            or "reservation confirmed" in current_url
        )

    def _wait_for_booking_confirmation(self, timeout_seconds: int = 12) -> bool:
        end_time = time.time() + timeout_seconds
        while time.time() < end_time:
            if self._is_booking_confirmed():
                return True
            time.sleep(1)
        return self._is_booking_confirmed()

    def complete_booking(self) -> bool:
        self._update_status("Completing booking...")
        time.sleep(2)

        submit_selectors = [
            (By.XPATH, "//button[contains(text(), 'Complete Reservation')]"),
            (By.XPATH, "//input[@value='Complete Reservation']"),
            (By.XPATH, "//button[contains(text(), 'Complete')]"),
            (By.ID, "s-lc-eq-bform-submit"),
            (By.CSS_SELECTOR, "button[type='submit']"),
            (By.XPATH, "//button[contains(text(), 'Submit')]"),
            (By.XPATH, "//button[contains(text(), 'Book')]"),
            (By.XPATH, "//button[contains(text(), 'Confirm')]"),
            (By.XPATH, "//input[@type='submit']"),
        ]

        for by, selector in submit_selectors:
            try:
                submit_btn = WebDriverWait(self.driver, 5).until(EC.element_to_be_clickable((by, selector)))
                self._update_status(f"Clicking '{submit_btn.text or submit_btn.get_attribute('value') or 'button'}'...")
                submit_btn.click()
                if self._wait_for_booking_confirmation():
                    self._update_status("Booking Confirmed page detected.")
                    return True
                self._update_status("Submit clicked, but Booking Confirmed page was not detected.")
            except (TimeoutException, NoSuchElementException):
                continue

        self._update_status("Could not confirm booking. Booking Confirmed page was not reached.")
        return False

    def _book_single_date(self, request: BookingRequest, booking_date, date_label: str = "") -> bool:
        prefix = f"[{date_label}] " if date_label else ""
        date_str = booking_date.strftime("%A, %B %d")

        self._update_status(f"{prefix}Booking for {date_str}...")
        self.driver.get(self._build_search_url(request, date_override=booking_date))
        time.sleep(3)

        rooms = self.find_available_rooms(request)
        if not rooms:
            self._update_status(f"{prefix}No available rooms found for {date_str}.")
            return False

        room = self._select_preferred_room(rooms)
        self._update_status(f"{prefix}Booking: {room['name']}")

        try:
            room['button'].click()
            self._update_status(f"{prefix}Clicked 'Book Now' button!")
            time.sleep(3)

            if self._handle_login_if_needed(prefix):
                time.sleep(2)

            for _ in range(3):
                if self.complete_booking():
                    self._update_status(f"{prefix}Successfully booked {room['name']} for {date_str}!")
                    return True
                time.sleep(2)

            self._update_status(f"{prefix}Booking failed for {date_str}: Booking Confirmed page was not reached.")
            return False

        except Exception as e:
            self._update_status(f"{prefix}Error booking for {date_str}: {e}")
            return False

    def _handle_login_if_needed(self, prefix: str = "") -> bool:
        page_source = self.driver.page_source.lower()
        if not any(kw in page_source for kw in ["sign in", "log in", "netid", "webauth"]):
            return False

        self._update_status(f"{prefix}Login page detected...")
        login_selectors = [
            (By.XPATH, "//button[contains(text(), 'Login')]"),
            (By.XPATH, "//button[contains(text(), 'Log In')]"),
            (By.XPATH, "//button[contains(text(), 'Sign In')]"),
            (By.XPATH, "//input[@value='Login']"),
            (By.XPATH, "//button[@type='submit']"),
            (By.CSS_SELECTOR, "button.btn-primary"),
        ]

        for by, selector in login_selectors:
            try:
                login_btn = WebDriverWait(self.driver, 2).until(EC.element_to_be_clickable((by, selector)))
                self._update_status(f"{prefix}Clicking '{login_btn.text or 'Login'}' button...")
                login_btn.click()
                time.sleep(3)
                return True
            except (TimeoutException, NoSuchElementException):
                continue

        self._update_status("Please click Login manually, then press Enter...")
        self._wait_for_user_confirmation("")
        return True

    def book_room(self, request: BookingRequest) -> bool:
        try:
            self.start_browser()
            self._update_status("Checking login status...")
            self.driver.get(self.BASE_URL)
            time.sleep(2)

            if self._handle_login_if_needed():
                self._update_status("Please log in using the Chrome window, then press Enter...")
                self._wait_for_user_confirmation("")
                time.sleep(2)

            if request.dates:
                return self._book_recurring(request)
            else:
                booking_date = request.date or datetime.now()
                success = self._book_single_date(request, booking_date)
                if not success:
                    self._update_status("Please try different dates/times or check the website manually.")
                self._wait_for_user_confirmation("Press Enter to close the browser...")
                return success

        except Exception as e:
            self._update_status(f"Booking error: {str(e)}")
            return False
        finally:
            if not self.keep_browser_open:
                self.close_browser()

    def _book_recurring(self, request: BookingRequest) -> bool:
        total = len(request.dates)
        self._update_status(f"\nRECURRING BOOKING: {total} dates")
        for i, d in enumerate(request.dates, 1):
            self._update_status(f"  {i}. {d.strftime('%A, %B %d, %Y')}")

        successful = sum(
            1 for i, booking_date in enumerate(request.dates, 1)
            if self._book_single_date(request, booking_date, f"{i}/{total}") or not time.sleep(2)
        )

        self._update_status(f"\nBOOKING SUMMARY: {successful}/{total} successful")
        self._wait_for_user_confirmation("Press Enter to close the browser...")
        return successful == total


if __name__ == "__main__":
    from parser import NaturalLanguageParser
    parser = NaturalLanguageParser()
    request = parser.parse("room for 4 people on Tuesday at 4pm")
    print(f"Parsed request:\n{request}\n\nStarting automation...")
    BookingAutomation(headless=False).book_room(request)
