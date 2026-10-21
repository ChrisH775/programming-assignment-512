"""Run with python -m unittest -v test_booking. No real accounts are used."""
import os
import secrets
import tempfile
import unittest
from datetime import datetime, timedelta
from booking import BookingSystem, Lecturer, CampusAdministrator, SystemOperator


class BookingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ["CAMPUS_TEST_PASSWORD"] = secrets.token_urlsafe(18)

    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.filename = os.path.join(self.folder.name, "test.db")
        self.system = BookingSystem(self.filename)
        self.system.setup(os.environ["CAMPUS_TEST_PASSWORD"])
        self.system.register("lecturer", os.environ["CAMPUS_TEST_PASSWORD"])
        self.lecturer = self.system.login("lecturer", os.environ["CAMPUS_TEST_PASSWORD"])
        self.admin = self.system.login("admin1", os.environ["CAMPUS_TEST_PASSWORD"])
        self.operator = self.system.login("operator", os.environ["CAMPUS_TEST_PASSWORD"])
        self.date = (datetime.now() + timedelta(days=2)).strftime("%Y-%m-%d")

    def tearDown(self):
        self.system.close()
        self.folder.cleanup()

    def book(self, time="10:00", duration="60", campus=1, resource=1):
        return self.system.book(self.lecturer, campus, resource, self.date, time, duration)

    def test_roles_and_campus_scope(self):
        self.assertIsInstance(self.lecturer, Lecturer)
        self.assertIsInstance(self.admin, CampusAdministrator)
        self.assertIsInstance(self.operator, SystemOperator)
        self.assertEqual(len(self.system.campuses(self.lecturer)), 3)
        self.assertEqual(len(self.system.campuses(self.admin)), 1)
        with self.assertRaises(ValueError):
            self.system.resources(self.admin, 2)
        with self.assertRaises(ValueError):
            self.system.report(self.admin, 2)
        with self.assertRaises(ValueError):
            self.system.save_resource(self.lecturer, 1, "Test")

    def test_login_and_duplicate_user(self):
        with self.assertRaises(ValueError):
            self.system.login("missing", "")
        with self.assertRaises(ValueError):
            self.system.login("lecturer", "")
        with self.assertRaises(ValueError):
            self.system.register("LECTURER", os.environ["CAMPUS_TEST_PASSWORD"])
        with self.assertRaises(ValueError):
            self.system.register("new", "")
        self.book()  # A rejected registration must not leave a transaction open.

    def test_password_not_stored_as_plain_text(self):
        row = self.system.db.execute("SELECT password_hash, salt FROM users LIMIT 1").fetchone()
        self.assertNotEqual(row["password_hash"], os.environ["CAMPUS_TEST_PASSWORD"])
        self.assertEqual(len(row["salt"]), 32)
        hashes = self.system.db.execute("SELECT password_hash FROM users").fetchall()
        self.assertEqual(len({row["password_hash"] for row in hashes}), 5)

    def test_setup_cannot_be_repeated(self):
        with self.assertRaises(ValueError):
            self.system.setup(os.environ["CAMPUS_TEST_PASSWORD"])

    def test_resource_add_update_remove_and_duplicate(self):
        self.system.save_resource(self.admin, 1, "Microphone")
        resource = self.system.resources(self.admin, 1)[-1]
        with self.assertRaises(ValueError):
            self.system.save_resource(self.admin, 1, "microphone")
        self.system.save_resource(self.admin, 1, "Microphone 2", resource["id"])
        self.system.remove_resource(self.admin, 1, resource["id"])
        self.assertEqual(len(self.system.resources(self.admin, 1)), 3)
        with self.assertRaises(ValueError):
            self.system.save_resource(self.admin, 2, "Not allowed")
        self.book()

    def test_overlap_and_adjacent_bookings(self):
        self.book()
        for time, duration in [("10:00", "60"), ("10:30", "60"), ("09:30", "60"), ("09:30", "120")]:
            with self.subTest(time=time, duration=duration):
                with self.assertRaises(ValueError):
                    self.book(time, duration)
        self.book("11:00")
        self.book("09:00")
        self.assertEqual(self.system.report(self.admin, 1)["total"], 3)

    def test_invalid_inputs(self):
        for date, time, minutes in [
            ("not a date", "10:00", "60"), (self.date, "25:00", "60"),
            (self.date, "10:00", "0"), (self.date, "10:00", "-1"),
            (self.date, "10:00", "1.5"), (self.date, "10:00", "abc"),
            ("2000-01-01", "10:00", "60"), (self.date, "07:59", "60"),
            (self.date, "16:30", "60"), (self.date, "10:00", "121"),
        ]:
            with self.subTest(date=date, time=time, minutes=minutes):
                with self.assertRaises(ValueError):
                    self.system.book(self.lecturer, 1, 1, date, time, minutes)

    def test_all_campus_policies(self):
        self.book("15:00", "120")
        self.book("15:00", "180", 2, 4)
        self.book("15:00", "60", 3, 7)
        with self.assertRaises(ValueError):
            self.book("09:00", "61", 3, 8)
        with self.assertRaises(ValueError):
            self.book("08:00", "30", 3, 8)

    def test_resource_must_belong_to_campus(self):
        with self.assertRaises(ValueError):
            self.book(campus=2, resource=1)
        with self.assertRaises(ValueError):
            self.book(resource=999)
        with self.assertRaises(ValueError):
            self.system.book(self.admin, 1, 1, self.date, "10:00", "60")

    def test_cancellation_frees_resource(self):
        booking_id = self.book()
        self.system.cancel(self.lecturer, booking_id)
        self.book()
        rows = self.system.bookings(self.lecturer, 1)
        self.assertEqual(sum(row["cancelled"] for row in rows), 1)
        self.assertEqual(self.system.report(self.admin, 1)["total"], 1)

    def test_cannot_cancel_other_users_or_past_bookings(self):
        self.system.register("other", os.environ["CAMPUS_TEST_PASSWORD"])
        other = self.system.login("other", os.environ["CAMPUS_TEST_PASSWORD"])
        booking_id = self.book()
        with self.assertRaises(ValueError):
            self.system.cancel(other, booking_id)
        self.assertEqual(self.system.bookings(other, 1), [])
        with self.assertRaises(ValueError):
            self.system.cancel(self.admin, booking_id)
        self.system.db.execute("UPDATE bookings SET start = '2000-01-01T10:00', end = '2000-01-01T11:00'")
        self.system.db.commit()
        with self.assertRaises(ValueError):
            self.system.cancel(self.lecturer, booking_id)

    def test_removal_preserves_history_and_blocks_future_bookings(self):
        self.book()
        with self.assertRaises(ValueError):
            self.system.remove_resource(self.admin, 1, 1)
        self.system.db.execute("UPDATE bookings SET start = '2000-01-01T10:00', end = '2000-01-01T11:00'")
        self.system.db.commit()
        self.system.remove_resource(self.admin, 1, 1)
        self.assertEqual(len(self.system.bookings(self.lecturer, 1)), 1)
        with self.assertRaises(ValueError):
            self.book()

    def test_report_totals_averages_and_months(self):
        self.book("10:00", "60")
        self.book("11:00", "30")
        cancelled = self.book("12:00", "90")
        self.system.cancel(self.lecturer, cancelled)
        report = self.system.report(self.admin, 1)
        self.assertEqual(report["total"], 2)
        self.assertEqual(report["minutes"], 90)
        self.assertEqual(report["average"], 45)
        self.assertEqual(report["most_used"], "Computer Lab 1")
        self.assertEqual(report["months"][self.date[:7]], 2)
        self.assertEqual(self.system.report(self.operator, 3)["average"], 0)

    def test_persistence(self):
        self.book()
        self.system.close()
        self.system = BookingSystem(self.filename)
        user = self.system.login("lecturer", os.environ["CAMPUS_TEST_PASSWORD"])
        self.assertEqual(len(self.system.bookings(user, 1)), 1)
        self.assertFalse(self.system.needs_setup())

    def test_availability_after_booking(self):
        self.book()
        self.assertFalse(self.system.is_available(1, self.date + "T10:30", self.date + "T11:30"))
        self.assertTrue(self.system.is_available(1, self.date + "T11:00", self.date + "T12:00"))

    def test_another_instance_detects_overlap(self):
        other = BookingSystem(self.filename)
        try:
            self.book()
            with self.assertRaises(ValueError):
                other.book(self.lecturer, 1, 1, self.date, "10:30", "30")
        finally:
            other.close()


if __name__ == "__main__":
    unittest.main()
