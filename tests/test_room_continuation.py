import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from browser import BookingAutomation
from parser import BookingRequest


class RoomContinuationTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.history_path = Path(self.temp_dir.name) / "recent_bookings.json"
        self.status_lines = []
        self.automation = BookingAutomation(
            headless=True,
            interactive_mode=False,
            keep_browser_open=False,
            close_existing_browsers=False,
            status_callback=self.status_lines.append,
            history_path=self.history_path,
        )
        self.booking_date = datetime(2026, 3, 6)

    def tearDown(self):
        self.temp_dir.cleanup()

    def _write_history(self, records):
        self.history_path.write_text(json.dumps(records), encoding="utf-8")

    def _request(self, start_hour=21, start_minute=0, end_hour=23, end_minute=45):
        request = BookingRequest()
        request.date = self.booking_date
        request.capacity = 4
        request.start_hour = start_hour
        request.start_minute = start_minute
        request.end_hour = end_hour
        request.end_minute = end_minute
        return request

    def test_continuation_prefers_exact_previous_room(self):
        self._write_history([
            {
                "booked_at": "2026-03-06T17:00:00",
                "date": "2026-03-06",
                "start": "17:00",
                "end": "21:00",
                "room_name": "Room B539",
            }
        ])
        rooms = [
            {"name": "Room B540", "description": "window natural light"},
            {"name": "Room B539", "description": "window natural light"},
            {"name": "Room C539", "description": "window natural light"},
        ]

        selected = self.automation._select_preferred_room(rooms, self._request(), self.booking_date)

        self.assertEqual(selected["name"], "Room B539")

    def test_continuation_prefers_nearby_room_among_window_rooms(self):
        self._write_history([
            {
                "booked_at": "2026-03-06T17:00:00",
                "date": "2026-03-06",
                "start": "17:00",
                "end": "21:00",
                "room_name": "Room B539",
            }
        ])
        rooms = [
            {"name": "Room B560", "description": ""},
            {"name": "Room C539", "description": "window natural light"},
            {"name": "Room B538", "description": "window natural light"},
        ]

        selected = self.automation._select_preferred_room(rooms, self._request(), self.booking_date)

        self.assertEqual(selected["name"], "Room B538")

    def test_continuation_does_not_prioritize_non_window_room_over_window_room(self):
        self._write_history([
            {
                "booked_at": "2026-03-06T17:00:00",
                "date": "2026-03-06",
                "start": "17:00",
                "end": "21:00",
                "room_name": "Room B539",
            }
        ])
        rooms = [
            {"name": "Room B539", "description": ""},
            {"name": "Room B538", "description": ""},
            {"name": "Room C539", "description": "window natural light"},
        ]

        selected = self.automation._select_preferred_room(rooms, self._request(), self.booking_date)

        self.assertEqual(selected["name"], "Room C539")

    def test_continuation_can_use_non_window_room_when_no_window_rooms_exist(self):
        self._write_history([
            {
                "booked_at": "2026-03-06T17:00:00",
                "date": "2026-03-06",
                "start": "17:00",
                "end": "21:00",
                "room_name": "Room B539",
            }
        ])
        rooms = [
            {"name": "Room C539", "description": ""},
            {"name": "Room B538", "description": ""},
        ]

        selected = self.automation._select_preferred_room(rooms, self._request(), self.booking_date)

        self.assertEqual(selected["name"], "Room B538")

    def test_non_continuation_uses_existing_window_preference(self):
        self._write_history([
            {
                "booked_at": "2026-03-06T17:00:00",
                "date": "2026-03-06",
                "start": "17:00",
                "end": "21:00",
                "room_name": "Room B539",
            }
        ])
        rooms = [
            {"name": "Room B538", "description": ""},
            {"name": "Room C539", "description": "window natural light"},
        ]

        selected = self.automation._select_preferred_room(
            rooms,
            self._request(start_hour=16, end_hour=17),
            self.booking_date,
        )

        self.assertEqual(selected["name"], "Room C539")

    def test_far_same_floor_room_is_not_treated_as_nearby(self):
        self._write_history([
            {
                "booked_at": "2026-03-06T17:00:00",
                "date": "2026-03-06",
                "start": "17:00",
                "end": "21:00",
                "room_name": "Room B539",
            }
        ])
        rooms = [
            {"name": "Room B560", "description": ""},
            {"name": "Room C539", "description": "window natural light"},
        ]

        selected = self.automation._select_preferred_room(rooms, self._request(), self.booking_date)

        self.assertEqual(selected["name"], "Room C539")

    def test_successful_booking_is_recorded_for_later_continuation(self):
        request = self._request(start_hour=17, end_hour=21, end_minute=0)
        room = {"name": "Room B539", "description": ""}

        self.automation._record_successful_booking(request, self.booking_date, room)

        history = json.loads(self.history_path.read_text(encoding="utf-8"))
        self.assertEqual(history[0]["date"], "2026-03-06")
        self.assertEqual(history[0]["start"], "17:00")
        self.assertEqual(history[0]["end"], "21:00")
        self.assertEqual(history[0]["room_name"], "Room B539")
        self.assertEqual(history[0]["room_code"], "B539")


if __name__ == "__main__":
    unittest.main()
