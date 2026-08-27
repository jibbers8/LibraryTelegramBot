import unittest

from booking_service import BookingService


class FakeAutomation:
    instances = []
    outcomes = []

    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.recurring_failed_dates = []
        FakeAutomation.instances.append(self)

    def _build_search_params(self, request):
        return {
            "capacity": request.capacity,
            "date": request.date.strftime("%Y-%m-%d") if request.date else "default",
            "start": f"{request.start_hour:02d}:{request.start_minute:02d}" if request.start_hour is not None else "default",
            "end": f"{request.end_hour:02d}:{request.end_minute:02d}" if request.end_hour is not None else "default",
        }

    def book_room(self, request):
        self.request = request
        if FakeAutomation.outcomes:
            return FakeAutomation.outcomes.pop(0)
        return True


class CompoundBookingTests(unittest.TestCase):
    def setUp(self):
        FakeAutomation.instances = []
        FakeAutomation.outcomes = []
        self.service = BookingService(automation_factory=FakeAutomation)

    def _run(self, text):
        return self.service.run_from_text(
            text,
            headless=False,
            interactive_mode=False,
            keep_browser_open=False,
            close_existing_browsers=False,
            accept_similar_times=True,
        )

    def test_uppercase_and_splits_into_multiple_booking_requests(self):
        result = self._run(
            "book for 8 people today 5pm to 9pm AND "
            "book for 8 people tomorrow 3pm to 6pm"
        )

        self.assertTrue(result.success)
        self.assertEqual(len(result.child_results), 2)
        self.assertEqual(len(FakeAutomation.instances), 2)
        self.assertEqual(FakeAutomation.instances[0].request.capacity, 8)
        self.assertEqual(FakeAutomation.instances[0].request.start_hour, 17)
        self.assertEqual(FakeAutomation.instances[0].request.end_hour, 21)
        self.assertEqual(FakeAutomation.instances[1].request.capacity, 8)
        self.assertEqual(FakeAutomation.instances[1].request.start_hour, 15)
        self.assertEqual(FakeAutomation.instances[1].request.end_hour, 18)

    def test_later_compound_clause_can_inherit_capacity(self):
        result = self._run(
            "book for 8 people today 5pm to 9pm AND "
            "book tomorrow 3pm to 6pm"
        )

        self.assertTrue(result.success)
        self.assertEqual(FakeAutomation.instances[1].request.capacity, 8)

    def test_between_and_time_range_does_not_split(self):
        parts = self.service.split_compound_request("book for 4 people between 10am and 2pm tomorrow")

        self.assertEqual(parts, ["book for 4 people between 10am and 2pm tomorrow"])

    def test_lowercase_and_splits_when_next_clause_starts_with_book(self):
        parts = self.service.split_compound_request(
            "book for 4 people today 5pm to 7pm and book tomorrow 3pm to 5pm"
        )

        self.assertEqual(
            parts,
            [
                "book for 4 people today 5pm to 7pm",
                "book tomorrow 3pm to 5pm",
            ],
        )

    def test_compound_success_requires_all_children_to_succeed(self):
        FakeAutomation.outcomes = [True, False]

        result = self._run(
            "book for 8 people today 5pm to 9pm AND "
            "book for 8 people tomorrow 3pm to 6pm"
        )

        self.assertFalse(result.success)
        self.assertEqual(result.summary(), "Completed 1/2 booking requests.")


if __name__ == "__main__":
    unittest.main()
