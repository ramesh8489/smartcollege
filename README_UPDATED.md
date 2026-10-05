# Smart College – Enhanced ERP

This version keeps the existing Smart College workflow and adds professional academic/ERP features.

## Main updates

- Faculty Degree/Course -> Year/Class -> assigned Subject filtering remains timetable-driven.
- CAT 1/2/3 marks with separate Exam (40) and Assignment (10) fields.
- Faculty leave workflow: Faculty -> School Incharge -> Admin Leave Messages.
- Leave types: Casual, Medical, On Duty, Emergency.
- Optional supporting document for leave requests.
- Student professional profile fields: phone, parent details, admission date, active status.
- Faculty professional profile fields: phone, designation, joining date, active status.
- Subject academic metadata: course, year, semester, credits, theory/practical.
- Student promotion action from Django Admin.
- Exam Management model for CAT/semester/practical exams, room, invigilator and publish status.
- Targeted circulars by audience, school, degree and year.
- In-app notifications for approved leaves and published circulars.
- Notification inbox with mark-all-as-read.
- Existing attendance, timetable and Excel/PDF reports retained.

## First run after extracting

```cmd
D:
cd D:\DjangoProjects\SmartCollege
venv\Scripts\activate
python manage.py migrate
python manage.py check
python manage.py runserver
```

If the project is copied to a new location, update the path only; no new virtual environment is required if the existing environment already has the requirements installed.

## Admin additions

Django Admin now includes:
- Subject academic metadata
- Exam Management
- Notifications
- Student promotion action
- Faculty active/designation fields
- Student active/profile fields

## Important

The included SQLite database is the existing project database. Run `python manage.py migrate` once so the new migration files create the added fields/tables.


## Fees Management (New)

- Student-wise fee records with academic year and semester
- Tuition, examination, hostel, transport, library and other fee types
- Paid amount, outstanding balance and computed status
- Payment history with receipt number, payment mode and reference number
- Admin management through Django Admin
- Student/admin fee dashboard at `/fees/`
- Printable PDF payment receipt
- Overpayment validation prevents payments beyond the remaining balance

After extracting an updated ZIP, run:

```bat
python manage.py migrate
python manage.py check
python manage.py runserver
```

## Library Management (Integrated)
- Django app: `library`
- Admin label: **Library Management**
- Models: **Books**, **Book loans**
- URL: `/library/`
- Apply migration before first use: `python manage.py migrate library`
- Full check: `python manage.py check`
