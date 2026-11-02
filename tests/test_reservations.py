import json
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from reservations import add_reservation, load_reservations


class BookingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = str(Path(self.temp.name) / "bookings.json")
        self.option = {"object_id": 3, "date": "2026-11-03", "time_range": "19:00-20:00"}

    def book(self, **updates):
        return add_reservation(dict(self.option, **updates), "Demo", "demo@example.test", "test", self.path)

    def test_duplicate_and_overlaps_rejected_without_changing_file(self):
        self.book()
        before = Path(self.path).read_bytes()
        for time_range in ("19:00-20:00", "18:30-19:30", "19:30-20:30", "18:00-21:00", "19:15-19:45"):
            with self.subTest(time_range=time_range), self.assertRaises(ValueError):
                self.book(time_range=time_range)
            self.assertEqual(Path(self.path).read_bytes(), before)

    def test_adjacent_times_other_objects_and_dates_allowed(self):
        self.book()
        self.book(time_range="18:00-19:00")
        self.book(time_range="20:00-21:00")
        self.book(object_id=4)
        self.book(date="2026-11-04")
        self.assertEqual([r["id"] for r in load_reservations(self.path)], [1, 2, 3, 4, 5])

    def test_invalid_slots_do_not_create_file(self):
        for updates in ({"object_id": None}, {"date": None}, {"date": "bad"}, {"date": "2026-1-3"},
                        {"time_range": "25:00-26:00"}, {"time_range": "20:00-19:00"}):
            with self.subTest(updates=updates), self.assertRaises(ValueError):
                self.book(**updates)
        self.assertFalse(Path(self.path).exists())

    def test_corrupt_file_is_not_overwritten(self):
        Path(self.path).write_text("broken")
        with self.assertRaises(json.JSONDecodeError):
            self.book()
        self.assertEqual(Path(self.path).read_text(), "broken")

    def test_concurrent_sessions_only_save_once(self):
        def attempt(_):
            try:
                self.book()
                return True
            except ValueError:
                return False
        with ThreadPoolExecutor(max_workers=4) as pool:
            self.assertEqual(sum(pool.map(attempt, range(8))), 1)
        self.assertEqual(len(load_reservations(self.path)), 1)
