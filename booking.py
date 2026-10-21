"""Database and booking rules for the campus booking assignment."""
import hashlib
import hmac
import os
import sqlite3
from datetime import datetime, timedelta


class User:
    def __init__(self, user_id, username, role, campus_id):
        self.id = user_id
        self.username = username
        self._role = role
        self._campus_id = campus_id

    def role_name(self):
        return self._role

    def can_visit(self, campus_id):
        return True

    def can_manage(self, campus_id):
        return False


class Lecturer(User):
    def role_name(self):
        return "Lecturer"


class CampusAdministrator(User):
    def role_name(self):
        return "Campus Administrator"

    def can_visit(self, campus_id):
        return campus_id == self._campus_id

    def can_manage(self, campus_id):
        return self.can_visit(campus_id)


class SystemOperator(User):
    def role_name(self):
        return "System Operator"

    def can_manage(self, campus_id):
        return True


def check_booking_policy(campus, date, time, duration):
    """Return validated start and end times, or explain invalid input."""
    try:
        start = datetime.strptime(date + " " + time, "%Y-%m-%d %H:%M")
        minutes = int(duration)
    except (ValueError, TypeError):
        raise ValueError("Use date YYYY-MM-DD, time HH:MM and whole minutes.")
    if minutes < 1 or minutes > campus["max_minutes"]:
        raise ValueError("Duration must be 1 to " + str(campus["max_minutes"]) + " minutes.")
    end = start + timedelta(minutes=minutes)
    if start <= datetime.now():
        raise ValueError("Choose a future date and time.")
    if (end.date() != start.date()
            or start.strftime("%H:%M") < campus["opens"]
            or end.strftime("%H:%M") > campus["closes"]):
        raise ValueError("Booking must fit inside campus opening hours.")
    return start, end, minutes


class BookingSystem:
    def __init__(self, filename):
        self.db = sqlite3.connect(filename)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA foreign_keys = ON")
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS campuses (
                id INTEGER PRIMARY KEY, name TEXT UNIQUE NOT NULL,
                opens TEXT NOT NULL, closes TEXT NOT NULL,
                max_minutes INTEGER NOT NULL);
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY, username TEXT UNIQUE COLLATE NOCASE NOT NULL,
                password_hash TEXT NOT NULL, salt TEXT NOT NULL,
                role TEXT NOT NULL, campus_id INTEGER REFERENCES campuses(id));
            CREATE TABLE IF NOT EXISTS resources (
                id INTEGER PRIMARY KEY, campus_id INTEGER NOT NULL REFERENCES campuses(id),
                name TEXT NOT NULL COLLATE NOCASE, active INTEGER NOT NULL DEFAULT 1,
                UNIQUE(campus_id, name));
            CREATE TABLE IF NOT EXISTS bookings (
                id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id),
                resource_id INTEGER NOT NULL REFERENCES resources(id),
                start TEXT NOT NULL, end TEXT NOT NULL, duration INTEGER NOT NULL,
                cancelled INTEGER NOT NULL DEFAULT 0);
        """)
        if not self.db.execute("SELECT id FROM campuses").fetchone():
            campuses = [
                (1, "Durban", "08:00", "17:00", 120),
                (2, "Johannesburg", "08:00", "18:00", 180),
                (3, "Cape Town", "09:00", "16:00", 60),
            ]
            self.db.executemany("INSERT INTO campuses VALUES (?, ?, ?, ?, ?)", campuses)
            for campus in campuses:
                for name in ["Computer Lab 1", "Projector 1", "Seminar Room 1"]:
                    self.db.execute("INSERT INTO resources (campus_id, name) VALUES (?, ?)",
                                    (campus[0], name))
            self.db.commit()

    def needs_setup(self):
        return self.db.execute("SELECT id FROM users WHERE role = 'operator'").fetchone() is None

    def _add_user(self, username, password, role, campus_id=None):
        username = username.strip()
        if not username or len(username) > 40 or len(password) < 8:
            raise ValueError("Enter a username (1–40 characters) and password (8+ characters).")
        salt = os.urandom(16).hex()
        digest = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), 600000).hex()
        try:
            self.db.execute(
                "INSERT INTO users (username, password_hash, salt, role, campus_id) VALUES (?, ?, ?, ?, ?)",
                (username, digest, salt, role, campus_id))
        except sqlite3.IntegrityError:
            self.db.rollback()
            raise ValueError("That username is already used.")

    def setup(self, password):
        if not self.needs_setup():
            raise ValueError("Initial setup is already complete.")
        try:
            self._add_user("operator", password, "operator")
            for campus in self.db.execute("SELECT id FROM campuses").fetchall():
                self._add_user("admin" + str(campus["id"]), password, "admin", campus["id"])
            self.db.commit()
        except ValueError:
            self.db.rollback()
            raise

    def register(self, username, password):
        if self.needs_setup():
            raise ValueError("Complete initial setup first.")
        self._add_user(username, password, "lecturer")
        self.db.commit()

    def login(self, username, password):
        row = self.db.execute("SELECT * FROM users WHERE username = ?", (username.strip(),)).fetchone()
        if row:
            digest = hashlib.pbkdf2_hmac(
                "sha256", password.encode(), bytes.fromhex(row["salt"]), 600000).hex()
            if hmac.compare_digest(digest, row["password_hash"]):
                classes = {"lecturer": Lecturer, "admin": CampusAdministrator, "operator": SystemOperator}
                return classes[row["role"]](row["id"], row["username"], row["role"], row["campus_id"])
        raise ValueError("Incorrect username or password.")

    def campuses(self, user):
        result = []
        for row in self.db.execute("SELECT * FROM campuses ORDER BY id").fetchall():
            if user.can_visit(row["id"]):
                result.append(dict(row))
        return result

    def _campus(self, user, campus_id):
        if not user.can_visit(campus_id):
            raise ValueError("You do not have access to this campus.")
        row = self.db.execute("SELECT * FROM campuses WHERE id = ?", (campus_id,)).fetchone()
        if not row:
            raise ValueError("Campus not found.")
        return dict(row)

    def resources(self, user, campus_id):
        self._campus(user, campus_id)
        rows = self.db.execute(
            "SELECT * FROM resources WHERE campus_id = ? AND active = 1 ORDER BY id",
            (campus_id,)).fetchall()
        return [dict(row) for row in rows]

    def save_resource(self, user, campus_id, name, resource_id=None):
        self._campus(user, campus_id)
        if not user.can_manage(campus_id):
            raise ValueError("Only administrators and operators can manage resources.")
        name = name.strip()
        if not name or len(name) > 80:
            raise ValueError("Enter a resource name (1–80 characters).")
        try:
            if resource_id is None:
                self.db.execute("INSERT INTO resources (campus_id, name) VALUES (?, ?)", (campus_id, name))
            else:
                cursor = self.db.execute(
                    "UPDATE resources SET name = ? WHERE id = ? AND campus_id = ? AND active = 1",
                    (name, resource_id, campus_id))
                if cursor.rowcount == 0:
                    self.db.rollback()
                    raise ValueError("Select an active resource at this campus.")
            self.db.commit()
        except sqlite3.IntegrityError:
            self.db.rollback()
            raise ValueError("That resource name already exists at this campus (including removed resources).")

    def remove_resource(self, user, campus_id, resource_id):
        self._campus(user, campus_id)
        if not user.can_manage(campus_id):
            raise ValueError("You cannot remove resources.")
        resource = self.db.execute(
            "SELECT id FROM resources WHERE id = ? AND campus_id = ? AND active = 1",
            (resource_id, campus_id)).fetchone()
        if not resource:
            raise ValueError("Select an active resource.")
        now = datetime.now().isoformat(timespec="minutes")
        if self.db.execute(
                "SELECT id FROM bookings WHERE resource_id = ? AND cancelled = 0 AND end > ?",
                (resource_id, now)).fetchone():
            raise ValueError("Cannot remove a resource with current or future bookings.")
        self.db.execute("UPDATE resources SET active = 0 WHERE id = ?", (resource_id,))
        self.db.commit()

    def is_available(self, resource_id, start, end):
        row = self.db.execute(
            """SELECT id FROM bookings WHERE resource_id = ? AND cancelled = 0
               AND start < ? AND end > ?""", (resource_id, end, start)).fetchone()
        return row is None

    def book(self, user, campus_id, resource_id, date, time, duration):
        if not isinstance(user, Lecturer):
            raise ValueError("Only lecturers can create bookings.")
        campus = self._campus(user, campus_id)
        start, end, minutes = check_booking_policy(campus, date, time, duration)
        start_text = start.isoformat(timespec="minutes")
        end_text = end.isoformat(timespec="minutes")
        # Lock before checking so another instance cannot save an overlapping booking.
        try:
            self.db.execute("BEGIN IMMEDIATE")
            resource = self.db.execute(
                "SELECT id FROM resources WHERE id = ? AND campus_id = ? AND active = 1",
                (resource_id, campus_id)).fetchone()
            if not resource:
                raise ValueError("Select an active resource at this campus.")
            if not self.is_available(resource_id, start_text, end_text):
                raise ValueError("This resource already has an overlapping booking.")
            cursor = self.db.execute(
                "INSERT INTO bookings (user_id, resource_id, start, end, duration) VALUES (?, ?, ?, ?, ?)",
                (user.id, resource_id, start_text, end_text, minutes))
            self.db.commit()
            return cursor.lastrowid
        except (ValueError, sqlite3.Error):
            self.db.rollback()
            raise

    def bookings(self, user, campus_id):
        self._campus(user, campus_id)
        sql = """SELECT b.*, u.username, r.name, r.campus_id FROM bookings b
                 JOIN users u ON b.user_id = u.id JOIN resources r ON b.resource_id = r.id
                 WHERE r.campus_id = ?"""
        values = [campus_id]
        if isinstance(user, Lecturer):
            sql += " AND b.user_id = ?"
            values.append(user.id)
        return [dict(row) for row in self.db.execute(sql + " ORDER BY b.start DESC", values).fetchall()]

    def cancel(self, user, booking_id):
        if not isinstance(user, Lecturer):
            raise ValueError("Only lecturers can cancel their own future bookings.")
        row = self.db.execute("SELECT * FROM bookings WHERE id = ?", (booking_id,)).fetchone()
        if not row or row["user_id"] != user.id:
            raise ValueError("Select one of your own bookings.")
        if row["cancelled"] or datetime.fromisoformat(row["start"]) <= datetime.now():
            raise ValueError("Only future, non-cancelled bookings can be cancelled.")
        self.db.execute("UPDATE bookings SET cancelled = 1 WHERE id = ?", (booking_id,))
        self.db.commit()

    def report(self, user, campus_id):
        campus = self._campus(user, campus_id)
        if not user.can_manage(campus_id):
            raise ValueError("Reports are for administrators and operators.")
        counts = {}
        months = {}
        total_minutes = 0
        total = 0
        for booking in self.bookings(user, campus_id):
            if booking["cancelled"]:
                continue
            total += 1
            total_minutes += booking["duration"]
            name = booking["name"]
            counts[name] = counts.get(name, 0) + 1
            month = booking["start"][:7]
            months[month] = months.get(month, 0) + 1
        most_used = "None"
        if counts:
            highest = max(counts.values())
            most_used = ", ".join(name for name in counts if counts[name] == highest)
        average = total_minutes / total if total else 0
        return {"campus": campus, "total": total, "minutes": total_minutes,
                "average": average, "most_used": most_used, "months": months}

    def close(self):
        self.db.close()
