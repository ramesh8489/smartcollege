# SmartCollege — College Management System

A Django-based college management system with role-based dashboards for
Students, Faculty, and Admins: attendance tracking, marks entry, and
Excel/PDF report generation.

## Features

- **Login system** with automatic role detection (Student / Faculty / Admin)
  from a single login page.
- **Admin dashboard** — counts of students, faculty, departments, subjects,
  attendance and marks records, plus recent activity.
- **Student dashboard** — profile, attendance history, marks history, and
  downloadable Excel/PDF reports.
- **Faculty dashboard** — subject-wise attendance % and marks %, mark
  attendance, enter/edit marks, search & filter attendance/marks history,
  downloadable Excel reports.
- **Reports app** — Excel exports for student/faculty attendance and marks,
  plus a PDF attendance report for students.
- **Auto-provisioned logins** — creating a Student or Faculty record in
  `/admin/` now automatically creates their login account (username =
  roll number / faculty ID, a random password is shown once in the admin
  success message). No more records with no way to log in.
- **School → Course structure** — a School (the existing `Department` model,
  e.g. "School of Computer Science") can now offer multiple **Courses**
  (degree programs, e.g. "MSc AI & Data Science", "BSc Computer Science").
  Add Courses in `/admin/` → Students → Courses. Students pick their
  School and Course when registering (the course list filters
  automatically based on the selected school). **Course is mandatory**
  when registering as a student.
- **All 14 Takshashila University Schools + 81 Courses pre-loaded** — run:
  ```bash
  python manage.py seed_schools_courses
  ```
  This creates every School (Computational Engineering, Core Engineering,
  Computer Science, Basic Sciences, Agricultural Sciences, Commerce,
  Management Studies, Humanities, Social Sciences, Allied Health Sciences,
  Physiotherapy, Pharmacy, Nursing, and Takshashila Medical College) with
  their real degree programs. Safe to run more than once — it won't create
  duplicates. Your existing "Computer Science" department is automatically
  renamed to "School of Computer Science" and kept (Ramesh A, kumar, Arun
  Kumar, and "python programming" stay linked to it — nothing is lost).

  Note: the 3 programmes under "School of Core Engineering" (Mechanical,
  Civil, Electrical) weren't given exact official titles in the source
  list I worked from — I used standard names. Rename them in `/admin/` if
  your university's official titles differ.
- **SIF Number** — every student now has a unique SIF number (the
  university's admission number), collected at registration alongside
  roll number, and shown on their profile page.
  Student or Faculty at `/accounts/register/`. New accounts start as
  **pending** and cannot log in until an admin approves them from the
  "Pending Approvals" section on the admin dashboard (Approve / Reject
  buttons). Rejecting deletes the registration and its login cleanly.
  Accounts created directly through `/admin/` are auto-approved.

## Project structure

```
SmartCollege/
├── accounts/         # Login, logout, admin dashboard
│   └── management/commands/create_missing_logins.py
├── students/         # Student model, dashboard, profile, history
├── faculty/          # Faculty & Subject models, dashboard, attendance/marks entry
├── attendance/       # Attendance model (used by students/faculty apps)
├── marks/            # Marks model (used by students/faculty apps)
├── reports/          # Excel/PDF report generation
├── config/           # Django project settings/urls
├── manage.py
├── requirements.txt
└── db.sqlite3        # Your existing data (Computer Science dept, students, faculty)
```

## Setup

```bash
python -m venv venv
venv\Scripts\activate        # Windows
source venv/bin/activate     # macOS/Linux

pip install -r requirements.txt

python manage.py migrate     # applies the new Faculty.user field
python manage.py runserver
```

Then open **http://127.0.0.1:8000/accounts/login/**

## Timetable, period-wise attendance, circulars & School Incharge

One-time setup after `migrate`:

```bash
python manage.py seed_periods     # creates 8 hourly periods (9 AM - 6 PM, lunch gap after P4)
```

Edit the timings anytime in `/admin/` -> Timetable -> Periods.

- **School Incharge** - in `/admin/` -> Timetable -> School incharges, pick a
  School and a Faculty member. One incharge per school (and one school per
  faculty). That faculty then sees a **Timetable Builder** button on their dashboard.
- **Timetable Builder (School Incharge only)** - (1) add Classes = Course + Year,
  (2) assign Day + Period + Class + Subject + Faculty. The system blocks clashes:
  a class can't have two lessons in one period, and a faculty can't teach two
  classes in the same period. Only faculty/subjects/courses of the incharge's own
  school are selectable.
- **Faculty attendance is now hour-wise** - faculty pick a date and one of their
  own timetable slots (e.g. "Mon - P1 - MCA Year 1 - Data Structures"), the whole
  class roster appears, and they mark everyone Present/Absent and save once.
  The date must fall on the slot's weekday. The same faculty can teach MCA in
  period 1 and B.Sc CS in period 2. A class roster = approved students whose
  course and year match the class.
- **My Timetable** - each faculty can see their weekly schedule.
- **Circulars** - the admin posts circulars from the admin dashboard
  (Everyone / Students only / Faculty only). Students and faculty see the latest
  on their dashboard and all of them at `/timetable/circulars/`.

Note: attendance taken before this update has no period stored and still shows
normally.

## Full UI redesign + admin School/Degree/Class filters

The whole interface has been redesigned with a single shared design system
(`static/css/theme.css`, `templates/base.html`) — a proper sidebar
navigation (role-aware: different menu for admin/faculty/student), consistent
cards, tables, badges, buttons and a mobile-responsive layout (hamburger menu
under ~900px width). Login and Register got a matching split-screen design.

**Admin dashboard is now tabbed and drill-down:**
- **Overview** — School → Degree → Class dropdowns (each one filters the
  next) plus clickable rows, so you can drill from "all schools" down to one
  specific class, seeing student/faculty counts, average attendance and
  average marks at every level. At the class level you also see the full
  student roster and that class's weekly timetable.
- **Students** — searchable, paginated (20/page) list of every student,
  filterable by the same School/Degree/Class dropdowns, with an **Export
  Excel** button that respects whatever filter is active.
- **Faculty** — searchable list with each faculty's subjects and weekly
  teaching load.
- **Approvals** — the pending-registration list from before, now its own tab.
- **Circulars** — posting and viewing circulars, now its own tab.

No new setup step is needed for this — it's all in the same code you already
migrated and seeded.

## Marks entry is now degree-wise + class-wise (bulk)

Faculty -> Marks Entry now works like Mark Attendance: pick a **Subject**,
**Degree** and **Class (Year)**, and the whole class roster appears with
CAT 1/2/3 boxes (pre-filled if marks already exist). Save once for the
whole class. Leave a row blank to skip that student. Only approved
students in that exact degree + year show up.

## Fixes applied in this update

1. **Department name typo fixed** — it was stored as `"Name: Computer
   Science"`; now `"Computer Science"`.
2. **Faculty "kumar" couldn't log in** — there was no login account linked
   to that record. A `user` field was added to the `Faculty` model
   (mirroring `Student`), and a one-time backfill was run. New login:
   - **Username:** `fac001`
   - **Password:** `P0NPMHGB`

   Change this password after logging in (`/admin/` → Users → fac001).
3. **Faculty "Arun Kumar"** was already logging in as `faculty1` — that
   account is untouched, just now linked directly instead of matched by
   email.
4. **Student attendance PDF report** is now linked on the student
   dashboard (it existed in the backend but had no button before).
5. **Auto-login-creation** added to the admin for both Student and Faculty,
   so this gap can't happen again. If you ever add records another way
   (e.g. a data import) and some end up without a login, run:
   ```bash
   python manage.py create_missing_logins
   ```

## Notes

- `DEBUG = True` and a development `SECRET_KEY` are still in
  `config/settings.py` — fine for local use/demo, but change both before
  deploying anywhere public.
- Existing admin/faculty/student passwords you already had were **not**
  changed — only the previously-broken "kumar" account got a new one
  (above).


## Fees Management (New)

The updated ERP includes a role-aware Fees & Payments module:
- Student-wise fee records
- Tuition, examination, hostel, transport, library and other fee types
- Academic year, semester and due date tracking
- Paid amount, balance and payment status
- Payment history with receipt/reference details
- Admin management through Django Admin
- Student/admin dashboard at `/fees/`
- Printable PDF payment receipts
- Overpayment validation

After updating the project, run `python manage.py migrate`, `python manage.py check`, then `python manage.py runserver`.
