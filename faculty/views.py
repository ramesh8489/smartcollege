from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.utils import timezone

from .models import Faculty, Subject
from students.models import Student
from students.models import Course
from attendance.models import Attendance
from marks.models import Marks
from timetable.models import SchoolIncharge, Circular, Timetable, FacultyLeaveRequest


# ============================================================
# GET LOGGED-IN FACULTY
# ============================================================

def get_faculty_for_user(request):

    faculty = Faculty.objects.filter(
        user=request.user
    ).first()

    if faculty:
        return faculty

    # Fallback for older records created before accounts
    # were linked directly (matched by email instead).
    return Faculty.objects.filter(
        email=request.user.email
    ).first()


# ============================================================
# FACULTY DASHBOARD
# ============================================================

@login_required(login_url="/accounts/login/")
def dashboard(request):

    faculty = get_faculty_for_user(request)

    if faculty is None:
        return redirect("/students/")

    is_incharge = SchoolIncharge.objects.filter(
        faculty=faculty
    ).exists()

    recent_circulars = Circular.objects.filter(
        audience__in=["ALL", "FACULTY"]
    )[:3]

    subjects = Subject.objects.filter(
        faculty=faculty
    )

    students = Student.objects.filter(
        department=faculty.department
    )

    attendance_records = Attendance.objects.filter(
        subject__in=subjects
    ).select_related(
        "student",
        "subject"
    ).order_by(
        "-date"
    )

    total_students = students.count()

    total_subjects = subjects.count()

    total_attendance_records = attendance_records.count()

    total_present = attendance_records.filter(
        present=True
    ).count()

    if total_attendance_records > 0:

        average_attendance = round(
            (
                total_present
                / total_attendance_records
            ) * 100,
            2
        )

    else:

        average_attendance = 0


    # =========================================================
    # MARKS STATISTICS
    # =========================================================

    marks_records = Marks.objects.filter(
        subject__in=subjects
    ).select_related(
        "student",
        "subject"
    )

    total_marks_entries = marks_records.count()

    total_marks_percentage = 0

    for mark in marks_records:

        total = mark.grand_total

        percentage = (
            total / 150
        ) * 100

        total_marks_percentage += percentage

    if total_marks_entries > 0:

        average_marks = round(
            total_marks_percentage
            / total_marks_entries,
            2
        )

    else:

        average_marks = 0


    # =========================================================
    # SUBJECT-WISE STATISTICS
    # =========================================================

    subject_statistics = []

    for subject in subjects:

        subject_attendance = Attendance.objects.filter(
            subject=subject
        )

        subject_total = subject_attendance.count()

        subject_present = subject_attendance.filter(
            present=True
        ).count()

        if subject_total > 0:

            attendance_percentage = round(
                (
                    subject_present
                    / subject_total
                ) * 100,
                2
            )

        else:

            attendance_percentage = 0


        subject_marks = Marks.objects.filter(
            subject=subject
        )

        subject_marks_count = subject_marks.count()

        subject_marks_percentage_total = 0

        for mark in subject_marks:

            total = mark.grand_total

            percentage = (
                total / 150
            ) * 100

            subject_marks_percentage_total += percentage

        if subject_marks_count > 0:

            marks_percentage = round(
                subject_marks_percentage_total
                / subject_marks_count,
                2
            )

        else:

            marks_percentage = 0


        subject_statistics.append({

            "subject":
                subject,

            "attendance_percentage":
                attendance_percentage,

            "attendance_total":
                subject_total,

            "attendance_present":
                subject_present,

            "marks_percentage":
                marks_percentage,

            "marks_count":
                subject_marks_count,

        })

    # =========================================================
    # ASSIGNMENTS (FACULTY DASHBOARD)
    # =========================================================
    from assignments.models import Assignment, AssignmentSubmission
    from django.db.models import Q

    tt_subs = Timetable.objects.filter(faculty=faculty).values_list("subject_id", flat=True)
    assigned_subs = Subject.objects.filter(Q(faculty=faculty) | Q(id__in=tt_subs)).distinct()

    faculty_assignments_qs = Assignment.objects.filter(
        Q(faculty=faculty) | Q(subject__in=assigned_subs)
    ).distinct().select_related("subject", "course").order_by("-created_at")

    now = timezone.now()
    faculty_assignments_summary = []
    total_assignment_submissions = 0
    total_pending_submissions = 0
    total_evaluated_submissions = 0

    for a in faculty_assignments_qs:
        subs = a.submissions.all()
        sub_count = subs.count()
        pending_sub = subs.filter(status__in=["Submitted", "Late"]).count()
        eval_sub = subs.filter(status="Evaluated").count()

        total_assignment_submissions += sub_count
        total_pending_submissions += pending_sub
        total_evaluated_submissions += eval_sub

        faculty_assignments_summary.append({
            "assignment": a,
            "submissions_count": sub_count,
            "pending_count": pending_sub,
            "evaluated_count": eval_sub,
            "is_upcoming": a.submission_deadline >= now,
        })

    upcoming_deadlines = [item for item in faculty_assignments_summary if item["is_upcoming"]][:5]

    # =========================================================
    # STUDENT LEAVE REQUESTS (FACULTY DASHBOARD)
    # =========================================================
    from student_leave.models import StudentLeaveRequest

    taught_courses = Subject.objects.filter(faculty=faculty).values_list("course_id", flat=True)
    faculty_student_leaves = StudentLeaveRequest.objects.filter(
        Q(student__department=faculty.department) | Q(student__course_id__in=taught_courses)
    ).distinct().select_related("student__course", "student__department").order_by("-applied_date")

    faculty_pending_leaves = faculty_student_leaves.filter(status=StudentLeaveRequest.STATUS_PENDING)
    faculty_approved_leaves = faculty_student_leaves.filter(
        status__in=[
            StudentLeaveRequest.STATUS_FACULTY_APPROVED,
            StudentLeaveRequest.STATUS_INCHARGE_APPROVED,
            StudentLeaveRequest.STATUS_ADMIN_APPROVED,
        ]
    )
    faculty_rejected_leaves = faculty_student_leaves.filter(status=StudentLeaveRequest.STATUS_FACULTY_REJECTED)

    return render(
        request,
        "faculty/dashboard.html",
        {
            "faculty":
                faculty,

            "subjects":
                subjects,

            "students":
                students,

            "attendance_records":
                attendance_records,

            "total_students":
                total_students,

            "total_subjects":
                total_subjects,

            "total_marks_entries":
                total_marks_entries,

            "total_attendance_records":
                total_attendance_records,

            "average_attendance":
                average_attendance,

            "average_marks":
                average_marks,

            "subject_statistics":
                subject_statistics,

            "is_incharge":
                is_incharge,

            "recent_circulars":
                recent_circulars,

            "faculty_assignments_summary":
                faculty_assignments_summary,

            "upcoming_deadlines":
                upcoming_deadlines,

            "total_assignments_count":
                len(faculty_assignments_summary),

            "total_assignment_submissions":
                total_assignment_submissions,

            "total_pending_submissions":
                total_pending_submissions,

            "total_evaluated_submissions":
                total_evaluated_submissions,

            "student_leaves_pending_count":
                faculty_pending_leaves.count(),

            "student_leaves_approved_count":
                faculty_approved_leaves.count(),

            "student_leaves_rejected_count":
                faculty_rejected_leaves.count(),

            "recent_pending_student_leaves":
                faculty_pending_leaves[:5],
        }
    )


# ============================================================
# MARK ATTENDANCE (PERIOD-WISE, TIMETABLE-DRIVEN)
#
# Step 1: faculty picks a date + one of their timetable slots
#         (day / period / class / subject).
# Step 2: the whole class roster is shown; faculty marks each
#         student Present/Absent and saves in one go.
# ============================================================

WEEKDAY_CODES = ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"]


@login_required(login_url="/accounts/login/")
def mark_attendance(request):

    import datetime

    faculty = get_faculty_for_user(request)

    if faculty is None:
        return redirect("/students/")

    slots = Timetable.objects.filter(
        faculty=faculty
    ).select_related(
        "period",
        "school_class",
        "subject"
    )

    context = {
        "faculty": faculty,
        "slots": slots,
    }

    # -----------------------------------------------------------
    # SAVE ATTENDANCE (POST)
    # -----------------------------------------------------------

    if request.method == "POST":

        slot = slots.filter(
            id=request.POST.get("slot")
        ).first()

        date_str = request.POST.get("date", "")

        try:
            date = datetime.date.fromisoformat(date_str)
        except ValueError:
            date = None

        if slot is None or date is None:

            context["error"] = "Invalid class slot or date."

            return render(
                request,
                "faculty/mark_attendance.html",
                context
            )

        if WEEKDAY_CODES[date.weekday()] != slot.day_of_week:

            context["error"] = (
                f"That date is a "
                f"{date.strftime('%A')}, but this class is on "
                f"{slot.get_day_of_week_display()}."
            )

            return render(
                request,
                "faculty/mark_attendance.html",
                context
            )

        for student in slot.school_class.students:

            status = request.POST.get(f"status_{student.id}")

            if status not in ("present", "absent"):
                continue

            Attendance.objects.update_or_create(
                student=student,
                subject=slot.subject,
                date=date,
                period=slot.period,
                defaults={
                    "present": status == "present"
                }
            )

        return redirect(
            "/faculty/attendance-history/"
        )

    # -----------------------------------------------------------
    # SHOW ROSTER (GET with ?slot=&date=)
    # -----------------------------------------------------------

    slot_id = request.GET.get("slot")
    date_str = request.GET.get("date")

    if slot_id and date_str:

        slot = slots.filter(id=slot_id).first()

        try:
            date = datetime.date.fromisoformat(date_str)
        except ValueError:
            date = None

        if slot is None or date is None:

            context["error"] = "Invalid class slot or date."

        elif WEEKDAY_CODES[date.weekday()] != slot.day_of_week:

            context["error"] = (
                f"That date is a "
                f"{date.strftime('%A')}, but this class is on "
                f"{slot.get_day_of_week_display()}."
            )

        else:

            existing = {
                a.student_id: a.present
                for a in Attendance.objects.filter(
                    subject=slot.subject,
                    date=date,
                    period=slot.period
                )
            }

            roster = [
                {
                    "student": student,
                    "present": existing.get(student.id, True),
                }
                for student in slot.school_class.students.filter(
                    is_approved=True
                ).order_by("name")
            ]

            context["selected_slot"] = slot
            context["selected_date"] = date_str
            context["roster"] = roster

    return render(
        request,
        "faculty/mark_attendance.html",
        context
    )


# ============================================================
# ATTENDANCE HISTORY
# SEARCH + FILTERS
# ============================================================

@login_required(login_url="/accounts/login/")
def attendance_history(request):

    faculty = get_faculty_for_user(request)

    if faculty is None:
        return redirect("/students/")

    subjects = Subject.objects.filter(
        faculty=faculty
    )

    students = Student.objects.filter(
        department=faculty.department
    )

    attendance_records = Attendance.objects.filter(
        subject__in=subjects
    ).select_related(
        "student",
        "subject"
    ).order_by(
        "-date"
    )

    search = request.GET.get(
        "search",
        ""
    ).strip()

    if search:

        attendance_records = attendance_records.filter(
            student__name__icontains=search
        ) | attendance_records.filter(
            student__roll_no__icontains=search
        )

        attendance_records = attendance_records.distinct()

    student_id = request.GET.get(
        "student"
    )

    if student_id:

        attendance_records = attendance_records.filter(
            student_id=student_id
        )

    subject_id = request.GET.get(
        "subject"
    )

    if subject_id:

        attendance_records = attendance_records.filter(
            subject_id=subject_id,
            subject__faculty=faculty
        )

    date = request.GET.get(
        "date"
    )

    if date:

        attendance_records = attendance_records.filter(
            date=date
        )

    total_classes = attendance_records.count()

    present_classes = attendance_records.filter(
        present=True
    ).count()

    absent_classes = attendance_records.filter(
        present=False
    ).count()

    if total_classes > 0:

        attendance_percentage = round(
            (
                present_classes
                / total_classes
            ) * 100,
            2
        )

    else:

        attendance_percentage = 0

    return render(
        request,
        "faculty/attendance_history.html",
        {
            "faculty": faculty,
            "attendance_records": attendance_records,
            "students": students,
            "subjects": subjects,
            "selected_student": student_id,
            "selected_subject": subject_id,
            "selected_date": date,
            "search": search,
            "total_classes": total_classes,
            "present_classes": present_classes,
            "absent_classes": absent_classes,
            "attendance_percentage":
                attendance_percentage,
        }
    )


# ============================================================
# MARKS ENTRY (DEGREE-WISE + CLASS-WISE, BULK)
#
# Step 1: faculty picks a Subject they teach, then the Degree
#         (Course) and Class (Year) to mark.
# Step 2: the whole class roster is shown with CAT1/2/3 boxes
#         (pre-filled if marks already exist) and saved in one go.
# ============================================================

@login_required(login_url="/accounts/login/")
def marks_entry(request):

    faculty = get_faculty_for_user(request)

    if faculty is None:
        return redirect("/students/")

    # Only degrees/classes that this faculty actually teaches are shown.
    assigned_slots = Timetable.objects.filter(
        faculty=faculty
    ).select_related("school_class__course", "subject")

    courses = Course.objects.filter(
        id__in=assigned_slots.values("school_class__course_id")
    ).distinct().order_by("name")

    course_id = request.POST.get("course") or request.GET.get("course")
    year = request.POST.get("year") or request.GET.get("year")
    subject_id = request.POST.get("subject") or request.GET.get("subject")

    selected_course = courses.filter(id=course_id).first() if course_id else None

    years = []
    if selected_course:
        years = sorted(
            set(
                assigned_slots.filter(
                    school_class__course=selected_course
                ).values_list("school_class__year", flat=True)
            )
        )

    try:
        selected_year = int(year) if year else None
    except (TypeError, ValueError):
        selected_year = None

    # IMPORTANT: after degree + year are selected, subjects are restricted
    # to subjects actually assigned to this faculty for that exact class.
    class_slots = assigned_slots.filter(
        school_class__course=selected_course,
        school_class__year=selected_year,
    ) if selected_course and selected_year else assigned_slots.none()

    subjects = Subject.objects.filter(
        id__in=class_slots.values("subject_id")
    ).distinct().order_by("name")

    selected_subject = subjects.filter(id=subject_id).first() if subject_id else None

    context = {
        "faculty": faculty,
        "courses": courses,
        "years": years,
        "subjects": subjects,
        "selected_course": selected_course,
        "selected_year": str(selected_year) if selected_year else "",
        "selected_subject": selected_subject,
    }

    if request.method == "POST":

        if selected_course is None or selected_year is None or selected_subject is None:
            context["error"] = "Select a valid degree, year and subject assigned to your class."
            return render(request, "faculty/marks_entry.html", context)

        roster_students = Student.objects.filter(
            course=selected_course,
            year=selected_year,
            is_approved=True,
        ).order_by("name")

        saved = 0

        for student in roster_students:
            values = {}
            valid = True

            for field, maximum in (
                ("cat_1", 40), ("cat_2", 40), ("cat_3", 40),
                ("cat_1_assignment", 10), ("cat_2_assignment", 10),
                ("cat_3_assignment", 10),
            ):
                raw = request.POST.get(f"{field}_{student.id}", "").strip()
                if raw == "":
                    raw = "0"
                try:
                    value = int(raw)
                except ValueError:
                    valid = False
                    break
                if not 0 <= value <= maximum:
                    valid = False
                    break
                values[field] = value

            if not valid:
                continue

            # Do not create a completely untouched row.
            if all(v == 0 for v in values.values()):
                continue

            Marks.objects.update_or_create(
                student=student,
                subject=selected_subject,
                defaults=values,
            )
            saved += 1

        return redirect(
            f"/faculty/marks/?subject={selected_subject.id}"
            f"&course={selected_course.id}&year={selected_year}&saved={saved}"
        )

    if selected_subject:
        existing = {
            m.student_id: m
            for m in Marks.objects.filter(
                subject=selected_subject,
                student__course=selected_course,
                student__year=selected_year,
            )
        }

        context["roster"] = [
            {"student": student, "mark": existing.get(student.id)}
            for student in Student.objects.filter(
                course=selected_course,
                year=selected_year,
                is_approved=True,
            ).order_by("name")
        ]
        context["saved_count"] = request.GET.get("saved")

    return render(request, "faculty/marks_entry.html", context)


# ============================================================
# MARKS HISTORY
# SEARCH + SUBJECT + GRADE FILTER
# ============================================================

@login_required(login_url="/accounts/login/")
def marks_history(request):

    faculty = get_faculty_for_user(request)

    if faculty is None:
        return redirect("/students/")

    subjects = Subject.objects.filter(
        faculty=faculty
    )

    marks_records = Marks.objects.filter(
        subject__faculty=faculty
    ).select_related(
        "student",
        "subject"
    ).order_by(
        "student__name",
        "subject__name"
    )

    # ========================================================
    # STUDENT SEARCH
    # Name OR Roll Number
    # ========================================================

    search = request.GET.get(
        "search",
        ""
    ).strip()

    if search:

        marks_records = marks_records.filter(
            student__name__icontains=search
        ) | marks_records.filter(
            student__roll_no__icontains=search
        )

        marks_records = marks_records.distinct()


    # ========================================================
    # SUBJECT FILTER
    # ========================================================

    subject_id = request.GET.get(
        "subject",
        ""
    )

    if subject_id:

        marks_records = marks_records.filter(
            subject_id=subject_id,
            subject__faculty=faculty
        )


    # ========================================================
    # GRADE FILTER
    # ========================================================

    grade_filter = request.GET.get(
        "grade",
        ""
    ).strip()


    # ========================================================
    # CREATE MARKS SUMMARY
    # ========================================================

    marks_summary = []

    for mark in marks_records:

        total = mark.grand_total

        percentage = round(
            (total / 150) * 100,
            2
        )

        if percentage >= 90:

            grade = "A+"

        elif percentage >= 80:

            grade = "A"

        elif percentage >= 70:

            grade = "B"

        elif percentage >= 60:

            grade = "C"

        elif percentage >= 50:

            grade = "D"

        else:

            grade = "F"


        # ----------------------------------------------------
        # Apply Grade Filter
        # ----------------------------------------------------

        if grade_filter:

            if grade != grade_filter:

                continue


        marks_summary.append({

            "mark":
                mark,

            "total":
                total,

            "percentage":
                percentage,

            "grade":
                grade,

        })


    # ========================================================
    # MARKS HISTORY PAGE
    # ========================================================

    return render(
        request,
        "faculty/marks_history.html",
        {
            "faculty":
                faculty,

            "marks_summary":
                marks_summary,

            "subjects":
                subjects,

            "search":
                search,

            "selected_subject":
                subject_id,

            "selected_grade":
                grade_filter,
        }
    )


# ============================================================
# EDIT MARKS
# ============================================================

@login_required(login_url="/accounts/login/")
def edit_marks(request, mark_id):

    faculty = get_faculty_for_user(request)

    if faculty is None:
        return redirect("/students/")

    mark = Marks.objects.filter(
        id=mark_id,
        subject__faculty=faculty,
    ).select_related("student", "subject").first()

    if mark is None:
        return redirect("/faculty/marks-history/")

    if request.method == "POST":
        values = {}
        for field, maximum in (
            ("cat_1", 40), ("cat_1_assignment", 10),
            ("cat_2", 40), ("cat_2_assignment", 10),
            ("cat_3", 40), ("cat_3_assignment", 10),
        ):
            raw = request.POST.get(field, "").strip()
            try:
                value = int(raw)
            except (TypeError, ValueError):
                return render(request, "faculty/edit_marks.html", {
                    "faculty": faculty,
                    "mark": mark,
                    "error": f"{field.replace('_', ' ').title()} must be a valid number.",
                })
            if not 0 <= value <= maximum:
                return render(request, "faculty/edit_marks.html", {
                    "faculty": faculty,
                    "mark": mark,
                    "error": f"{field.replace('_', ' ').title()} must be between 0 and {maximum}.",
                })
            values[field] = value

        for field, value in values.items():
            setattr(mark, field, value)
        mark.save()

        return redirect("/faculty/marks-history/")

    return render(request, "faculty/edit_marks.html", {
        "faculty": faculty,
        "mark": mark,
    })


# ============================================================
# FACULTY LEAVE REQUEST
# ============================================================

@login_required(login_url="/accounts/login/")
def leave_request(request):

    faculty = get_faculty_for_user(request)
    if faculty is None:
        return redirect("/students/")

    if request.method == "POST":
        from_date = request.POST.get("from_date")
        to_date = request.POST.get("to_date")
        leave_type = request.POST.get("leave_type", "CASUAL")
        reason = request.POST.get("reason", "").strip()
        supporting_document = request.FILES.get("supporting_document")

        if not from_date or not to_date or not reason:
            return render(request, "faculty/leave_request.html", {
                "faculty": faculty,
                "error": "Please enter from date, to date and reason.",
                "requests": FacultyLeaveRequest.objects.filter(faculty=faculty),
            })

        if from_date > to_date:
            return render(request, "faculty/leave_request.html", {
                "faculty": faculty,
                "error": "To date must be on or after from date.",
                "requests": FacultyLeaveRequest.objects.filter(faculty=faculty),
            })

        FacultyLeaveRequest.objects.create(
            faculty=faculty,
            department=faculty.department,
            from_date=from_date,
            to_date=to_date,
            leave_type=leave_type,
            reason=reason,
            supporting_document=supporting_document,
        )
        return redirect("/faculty/leave-request/")

    return render(request, "faculty/leave_request.html", {
        "faculty": faculty,
        "requests": FacultyLeaveRequest.objects.filter(
            faculty=faculty
        ).select_related("reviewed_by"),
    })


# ============================================================
# FACULTY PROFILE
# ============================================================

@login_required(login_url="/accounts/login/")
def profile(request):

    faculty = get_faculty_for_user(request)

    if faculty is None:
        return redirect("/students/")

    subjects = Subject.objects.filter(
        faculty=faculty
    ).select_related(
        "department"
    )

    return render(
        request,
        "faculty/profile.html",
        {
            "faculty": faculty,
            "subjects": subjects,
        }
    )
