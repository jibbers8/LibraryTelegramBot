import unittest

from parser import NaturalLanguageParser


class DateInterpretationTests(unittest.TestCase):
    def test_this_and_next_weekday_are_not_same(self):
        parser = NaturalLanguageParser()
        this_tuesday = parser.parse("this tuesday at 4pm").date
        next_tuesday = parser.parse("next tuesday at 4pm").date
        self.assertIsNotNone(this_tuesday)
        self.assertIsNotNone(next_tuesday)
        self.assertNotEqual(this_tuesday.date(), next_tuesday.date())
        self.assertEqual((next_tuesday.date() - this_tuesday.date()).days, 7)


if __name__ == "__main__":
    unittest.main()
