# Smart Campus Resource Booking System
Programming 512 — a simple Python, Tkinter and SQLite desktop project.

## Run
Install Python 3 with Tkinter (included in the standard Windows installer).
Open a terminal in this folder and run `python main.py`.
No pip packages are needed for the application.

## First run
Choose a private setup password of at least eight characters and confirm it.
The application creates four local demonstration accounts with that password:
- `operator`: system-wide access.
- `admin1`: Durban administrator.
- `admin2`: Johannesburg administrator.
- `admin3`: Cape Town administrator.

Use **Register lecturer** to create lecturer accounts. Registration cannot create
privileged accounts. Passwords are salted and hashed, not stored as plain text.
The shared setup password is a classroom simplification; this is not a production
identity-management system. Never use real institutional passwords or personal
student information in this demonstration.

## Use
1. Log in and select a campus from the **Active campus** list.
2. Read the displayed campus policy.
3. Enter a future date (`YYYY-MM-DD`), start time (`HH:MM`, 24-hour clock) and
   duration in whole minutes.
4. Click **Check selected time**, select an available resource and click
   **Book selected resource**. Availability is checked again when saving.
5. Open **My bookings** to filter active, past or cancelled bookings.
   Select a future booking to cancel it. Switch campuses to see other history.
6. Administrators can add, update or remove resources and view campus bookings
   and reports. Select a resource row to load its name for editing.
7. Operators can also compare all campuses in **Reports**.

**Active** includes future and currently running bookings. A removed resource is
hidden, but its history remains. Removal is blocked while it has current or
future bookings. Resource names, including removed names, cannot be duplicated
within the same campus; use a distinct name for replacement equipment.

## Demonstration campus policies
- Durban: 08:00–17:00; maximum 120 minutes per session.
- Johannesburg: 08:00–18:00; maximum 180 minutes.
- Cape Town: 09:00–16:00; maximum 60 minutes.

These are sample assignment policies, not official Richfield policies.
Times use the computer's local clock. Sessions must fit within one day's hours.
Adjacent bookings are allowed; overlapping bookings for one resource are rejected.
Availability refreshes every ten seconds and when an action changes bookings.
**Show availability now** checks current usage; **Check selected time** checks
the requested interval. Check again after changing the date, time or duration.

Reports cover all dates, exclude cancelled bookings and include future
reservations. They show booking counts, total reserved minutes, most-used
resources, average duration and monthly counts. They do not measure attendance
or claim that campus policy causes differences.

## Files and storage
- `main.py`: Tkinter screens.
- `booking.py`: role classes, validation, SQLite operations and reporting.
- `test_booking.py`: automated tests using a separate temporary database.
- `campus_booking.db`: created automatically beside the program; all users,
  campus policies, resources and bookings persist here between runs.

Keep a backup of your local database if you need its records. Do not publish it.
To add campuses later, add their database records and initial resources; the GUI
loads campus choices and policy values from the database. Campus policies are
validated separately in `check_booking_policy`.

## Tests
Run `python -m unittest -v test_booking` in this folder.
Tests do not change the application's database.

## Learning references and assistance
The project uses beginner concepts demonstrated in these tutorials. The booking
application is an original adaptation, not a copied tutorial project.
- freeCodeCamp.org (2019), *Tkinter Course - Create Graphic User Interfaces in
  Python Tutorial*: https://www.youtube.com/watch?v=YXPyB4XeYLA
- freeCodeCamp.org (n.d.), *SQLite Databases With Python - Full Course*:
  https://www.youtube.com/watch?v=byHcYRpMgI4
- Schafer, C. (n.d.), *Python OOP Tutorial 1: Classes and Instances*:
  https://www.youtube.com/watch?v=ZDa-Z5JzLYM

AI assistance (Warp) was used to develop and test this educational example and
prepare its documentation. Review the code, understand it, and follow your
institution's rules for acknowledging assistance before submitting.

## GitHub
Public repository: https://github.com/ChrisH775/programming-assignment-512

## Submission
The local assignment Word/PDF documents and screenshots are deliberately excluded
from the public repository. The submission ZIP should contain those documents
along with the source and README, but no Git metadata, runtime database or caches.
Complete the cover details, review the originality declaration and sign it yourself.
