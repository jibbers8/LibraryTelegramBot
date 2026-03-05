import re
from datetime import datetime, timedelta
from typing import Optional
import dateparser


class BookingRequest:
    def __init__(self):
        self.capacity: Optional[int] = None
        self.date: Optional[datetime] = None
        self.dates: list[datetime] = []
        self.time_preference: Optional[str] = None
        self.target_hour: Optional[int] = None
        self.target_minute: int = 0
        self.start_hour: Optional[int] = None
        self.start_minute: int = 0
        self.end_hour: Optional[int] = None
        self.end_minute: int = 0
        self.room_type: Optional[str] = None
        self.floor: Optional[int] = None
        self.duration_hours: int = 1

    def _format_hour(self, hour: int, minute: int = 0) -> str:
        return f"{hour % 12 or 12}:{minute:02d} {'AM' if hour < 12 else 'PM'}"

    def __str__(self) -> str:
        parts = []
        if self.capacity:
            parts.append(f"Capacity: {self.capacity} people")
        if self.dates:
            parts.append(f"Dates: {len(self.dates)} bookings")
            parts.extend(f"  {i}. {d.strftime('%A, %B %d, %Y')}" for i, d in enumerate(self.dates, 1))
        elif self.date:
            parts.append(f"Date: {self.date.strftime('%A, %B %d, %Y')}")
        if self.start_hour is not None and self.end_hour is not None:
            parts.append(
                f"Time: {self._format_hour(self.start_hour, self.start_minute)} "
                f"to {self._format_hour(self.end_hour, self.end_minute)}"
            )
        elif self.target_hour is not None:
            parts.append(f"Time: around {self._format_hour(self.target_hour, self.target_minute)}")
        elif self.time_preference:
            parts.append(f"Time: {self.time_preference}")
        if self.room_type:
            parts.append(f"Room type: {self.room_type}")
        if self.floor:
            parts.append(f"Floor: {self.floor}")
        if self.duration_hours > 1:
            parts.append(f"Duration: {self.duration_hours} hours")
        return "\n".join(parts) if parts else "No specific requirements"


class NaturalLanguageParser:
    CAPACITY_PATTERNS = [
        r'(\d+)\s*(?:people|persons|students|members|of us)',
        r'(?:for|need|want)\s*(\d+)(?!\s*(?:weeks?|days?|hours?|minutes?))',
        r'group\s*(?:of\s*)?(\d+)',
        r'(\d+)\s*(?:person|student|member)\s*(?:room|space)?',
        r'room\s*for\s*(\d+)',
    ]

    TIME_PATTERNS = [
        r'(\d{1,2})\s*(?::(\d{2}))?\s*(am|pm|AM|PM)',
        r'(\d{1,2})\s*(?::(\d{2}))?\s*(?:o\'?clock)?',
        r'around\s*(\d{1,2})\s*(am|pm|AM|PM)?',
        r'at\s*(\d{1,2})\s*(am|pm|AM|PM)?',
    ]

    TIME_OF_DAY = {
        'morning': (8, 11), 'afternoon': (12, 16), 'evening': (17, 20),
        'night': (18, 21), 'noon': (12, 12), 'midday': (12, 12), 'lunch': (11, 13),
    }

    ROOM_TYPE_KEYWORDS = {
        'quiet': ['quiet', 'silent', 'individual', 'solo', 'alone', 'by myself'],
        'group': ['group', 'team', 'collaborative', 'together'],
        'video': ['video', 'conference', 'zoom', 'call', 'meeting', 'virtual'],
        'presentation': ['presentation', 'present', 'projector', 'screen', 'display'],
    }

    WORD_NUMBERS = {
        'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5,
        'six': 6, 'seven': 7, 'eight': 8, 'nine': 9, 'ten': 10,
        'eleven': 11, 'twelve': 12
    }
    WEEKDAYS = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']

    def parse(self, text: str) -> BookingRequest:
        request = BookingRequest()
        text_lower = text.lower()

        request.capacity = self._extract_capacity(text_lower)
        request.dates = self._extract_recurring_dates(text_lower)
        if not request.dates:
            request.date = self._extract_date(text)

        time_result, time_pref = self._extract_time(text_lower)
        if time_pref == "range" and isinstance(time_result, tuple):
            (request.start_hour, request.start_minute), (request.end_hour, request.end_minute) = time_result
        elif isinstance(time_result, tuple):
            request.target_hour, request.target_minute = time_result
            request.time_preference = time_pref

        request.room_type = self._extract_room_type(text_lower)
        request.floor = self._extract_floor(text_lower)
        request.duration_hours = self._extract_duration(text_lower)

        return request

    def _extract_capacity(self, text: str) -> Optional[int]:
        for pattern in self.CAPACITY_PATTERNS:
            match = re.search(pattern, text)
            if match:
                return int(match.group(1))

        for word, num in self.WORD_NUMBERS.items():
            if re.search(rf'{word}\s*(?:people|persons|students|of us)', text):
                return num
        return None

    def _extract_recurring_dates(self, text: str) -> list[datetime]:
        days_of_week = {d: i for i, d in enumerate(['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday'])}
        days_of_week.update({d + 's': i for d, i in days_of_week.items()})

        patterns = [
            (r'(?:the\s+)?next\s+(\d+)\s+(mondays?|tuesdays?|wednesdays?|thursdays?|fridays?|saturdays?|sundays?)', False),
            (r'(\d+)\s+(mondays?|tuesdays?|wednesdays?|thursdays?|fridays?|saturdays?|sundays?)', False),
            (r'every\s+(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\s+for\s+(\d+)\s+weeks?', True),
        ]

        for pattern, swap_groups in patterns:
            match = re.search(pattern, text.lower())
            if match:
                groups = match.groups()
                count, day_name = (int(groups[1]), groups[0]) if swap_groups else (int(groups[0]), groups[1])
                target_weekday = days_of_week.get(day_name.rstrip('s'))
                if target_weekday is None:
                    continue

                today = datetime.now()
                days_until = (target_weekday - today.weekday()) % 7 or 7
                return [today + timedelta(days=days_until + (i * 7)) for i in range(count)]

        return []

    def _extract_date(self, text: str) -> Optional[datetime]:
        text_lower = text.lower()
        today = datetime.now()

        this_match = re.search(r'\bthis\s+(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b', text_lower)
        if this_match:
            target_weekday = self.WEEKDAYS.index(this_match.group(1))
            days_until = (target_weekday - today.weekday()) % 7
            return (today + timedelta(days=days_until)).replace(hour=0, minute=0, second=0, microsecond=0)

        next_match = re.search(r'\bnext\s+(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b', text_lower)
        if next_match:
            target_weekday = self.WEEKDAYS.index(next_match.group(1))
            days_until = (target_weekday - today.weekday()) % 7
            return (today + timedelta(days=days_until + 7)).replace(hour=0, minute=0, second=0, microsecond=0)

        date_patterns = [
            r'\b(today|tomorrow|tonight)\b',
            r'\b(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b',
            r'\b(next\s+(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday))\b',
            r'\b(this\s+(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday))\b',
            r'\b(\d{1,2}[/-]\d{1,2}(?:[/-]\d{2,4})?)\b',
            r'\b((?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s+\d{1,2}(?:st|nd|rd|th)?(?:\s*,?\s*\d{4})?)\b',
        ]

        text_to_parse = text
        for pattern in date_patterns:
            match = re.search(pattern, text.lower())
            if match:
                text_to_parse = match.group(1)
                break

        parsed = dateparser.parse(text_to_parse, settings={
            'PREFER_DATES_FROM': 'future',
            'PREFER_DAY_OF_MONTH': 'first',
            'RETURN_AS_TIMEZONE_AWARE': False,
            'RELATIVE_BASE': today.replace(hour=0, minute=0, second=0, microsecond=0),
        })

        if parsed and parsed.date() < today.date():
            parsed += timedelta(days=7)
        return parsed

    def _parse_single_time(self, time_str: str) -> Optional[tuple[int, int]]:
        match = re.search(r'(\d{1,2})(?::(\d{2}))?\s*(am|pm)?', time_str.strip().lower())
        if not match:
            return None
        hour = int(match.group(1))
        minute = int(match.group(2) or 0)
        if minute > 59:
            return None
        ampm = match.group(3)
        if ampm and (hour < 1 or hour > 12):
            return None
        if not ampm and hour > 23:
            return None
        if ampm == 'pm' and hour != 12:
            hour += 12
        elif ampm == 'am' and hour == 12:
            hour = 0
        elif not ampm and 1 <= hour <= 7:
            hour += 12
        return hour, minute

    def _extract_time(self, text: str):
        time_fragment = r'\d{1,2}(?::\d{2})?\s*(?:am|pm)?'
        range_patterns = [
            rf'from\s+({time_fragment})\s+to\s+({time_fragment})',
            rf'between\s+({time_fragment})\s+and\s+({time_fragment})',
            rf'\b({time_fragment})\s*(?:to|-)\s*({time_fragment})\b',
        ]

        for pattern in range_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                start, end = self._parse_single_time(match.group(1)), self._parse_single_time(match.group(2))
                if start is not None and end is not None:
                    return (start, end), "range"

        single_patterns = [
            r'(?:around|at)\s+(\d{1,2}(?::\d{2})?\s*(?:am|pm)?)',
            r'\b(\d{1,2}(?::\d{2})?\s*(?:am|pm))\b',
            r'\b(\d{1,2}(?::\d{2}))\b',
        ]

        for pattern in single_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                parsed = self._parse_single_time(match.group(1))
                if parsed is not None:
                    return parsed, None

        for period, (start, end) in self.TIME_OF_DAY.items():
            if period in text:
                return ((start + end) // 2, 0), period

        return None, None

    def _extract_room_type(self, text: str) -> Optional[str]:
        for room_type, keywords in self.ROOM_TYPE_KEYWORDS.items():
            if any(kw in text for kw in keywords):
                return room_type
        return None

    def _extract_floor(self, text: str) -> Optional[int]:
        match = re.search(r'(\d+)(?:st|nd|rd|th)?\s*floor|floor\s*(\d+)', text)
        if match:
            floor = int(match.group(1) or match.group(2))
            if 1 <= floor <= 5:
                return floor
        return None

    def _extract_duration(self, text: str) -> int:
        match = re.search(r'(?:for\s+)?(\d+)\s*hours?', text)
        return min(int(match.group(1)), 4) if match else 1


if __name__ == "__main__":
    parser = NaturalLanguageParser()
    tests = [
        "I need a room for 4 people on Tuesday around 4pm",
        "Book a quiet study space for tomorrow morning",
        "Group room for 6 students next Monday at 2pm for 2 hours",
    ]
    for text in tests:
        print(f"\nInput: {text}\n{'-' * 50}\n{parser.parse(text)}")
