import unittest
from datetime import datetime
from urllib.parse import urlparse, parse_qs

from browser import BookingAutomation
from parser import NaturalLanguageParser


class UrlMappingTests(unittest.TestCase):
    def setUp(self):
        self.parser = NaturalLanguageParser()
        self.automation = BookingAutomation(
            headless=True,
            interactive_mode=False,
            keep_browser_open=False,
            close_existing_browsers=False,
            status_callback=lambda _: None,
        )
        self.test_date = datetime(2026, 3, 4)

    def _qs(self, text: str):
        request = self.parser.parse(text)
        url = self.automation._build_search_url(request, date_override=self.test_date)
        return parse_qs(urlparse(url).query)

    def test_pm_range_maps_to_24h(self):
        qs = self._qs("room for 4 people from 8pm to 10pm")
        self.assertEqual(qs["start"][0], "20:00")
        self.assertEqual(qs["end"][0], "22:00")

    def test_pm_minute_range_maps_to_24h(self):
        qs = self._qs("room for 4 people from 10pm to 10:30pm")
        self.assertEqual(qs["start"][0], "22:00")
        self.assertEqual(qs["end"][0], "22:30")

    def test_am_to_afternoon_range_maps_exact(self):
        qs = self._qs("room for 4 people from 10am to 2pm")
        self.assertEqual(qs["start"][0], "10:00")
        self.assertEqual(qs["end"][0], "14:00")

    def test_capacity_url_codes(self):
        qs_two = self._qs("room for 2 people from 8pm to 9pm")
        qs_four = self._qs("room for 4 people from 8pm to 9pm")
        qs_eight = self._qs("room for 8 people from 8pm to 9pm")
        self.assertEqual(qs_two["capacity"][0], "1")
        self.assertEqual(qs_four["capacity"][0], "2")
        self.assertEqual(qs_eight["capacity"][0], "3")


if __name__ == "__main__":
    unittest.main()
