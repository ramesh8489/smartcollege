from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q, Avg, Count
from django.utils import timezone
from django.http import HttpResponseForbidden, JsonResponse
from decimal import Decimal

from .models import Exam, ExamSchedule, StudentExamMark, compute_grade_and_points
from .forms import ExamForm, ExamScheduleForm, StudentExamMarkForm
from students.models import Student, Course
from faculty.models import Faculty, Subject
from timetable.models import Notification, Timetable


def _get_faculty(user):
    return (
        Faculty.objects.filter(user=user).first()
        or Faculty.objects.filter(email=user.email).first()
    )


def _get_faculty_assigned_subjects(faculty):
    """
    Returns QuerySet of subjects assigned to the given faculty member.
    """
    if not faculty:
        return Subject.objects.none()
    timetable_subject_ids = Timetable.objects.filter(faculty=faculty).values_list("subject_id", flat=True)
    return Subject.objects.filter(Q(faculty=faculty) | Q(id__in=timetable_subject_ids)).distinct()


# ============================================================
# EXAM DASHBOARD / LIST
# ============================================================

@login_required(login_url="/accounts/login/")
def exam_list(request):
    """
    Exams Dashboard / List:
    - Admin: Full management with filtering, stats, creation and control.
    - Faculty: All exams with focus on department/courses.
    - Student: Filtered to student's enrolled course and academic year.
    """
    user = request.user
    student = Student.objects.filter(user=user).select_related("course", "department").first()
    is_admin = user.is_superuser or user.is_staff
    faculty = _get_faculty(user)
    is_faculty = faculty is not None

    queryset = Exam.objects.select_related("course", "course__department", "created_by").prefetch_related("schedules")

    if student and not (is_admin or is_faculty):
        # Student view: only active exams for student's course and year
        queryset = queryset.filter(
            course=student.course,
            year=student.year,
            is_active=True
        )

    # Filter parameters
    q = request.GET.get("q", "").strip()
    exam_type = request.GET.get("exam_type", "").strip()
    academic_year = request.GET.get("academic_year", "").strip()
    course_id = request.GET.get("course", "").strip()
    year = request.GET.get("year", "").strip()
    semester = request.GET.get("semester", "").strip()
    status = request.GET.get("status", "").strip()

    if q:
        queryset = queryset.filter(
            Q(name__icontains=q) |
            Q(description__icontains=q) |
            Q(course__name__icontains=q) |
            Q(academic_year__icontains=q)
        )

    if exam_type:
        queryset = queryset.filter(exam_type=exam_type)

    if academic_year:
        queryset = queryset.filter(academic_year=academic_year)

    if course_id:
        queryset = queryset.filter(course_id=course_id)

    if year:
        queryset = queryset.filter(year=year)

    if semester:
        queryset = queryset.filter(semester=semester)

    today = timezone.localdate()

    if status == "active":
        queryset = queryset.filter(is_active=True)
    elif status == "inactive":
        queryset = queryset.filter(is_active=False)
    elif status == "upcoming":
        queryset = queryset.filter(is_active=True, start_date__gt=today)
    elif status == "ongoing":
        queryset = queryset.filter(is_active=True, start_date__lte=today, end_date__gte=today)
    elif status == "completed":
        queryset = queryset.filter(end_date__lt=today)

    exams = list(queryset)

    # Calculate statistics across all relevant exams
    base_exams = Exam.objects.all() if (is_admin or is_faculty) else Exam.objects.filter(course=student.course if student else None)
    total_count = base_exams.count()
    active_count = base_exams.filter(is_active=True).count()
    upcoming_count = base_exams.filter(is_active=True, start_date__gt=today).count()
    ongoing_count = base_exams.filter(is_active=True, start_date__lte=today, end_date__gte=today).count()
    completed_count = base_exams.filter(end_date__lt=today).count()

    courses = Course.objects.all().select_related("department")
    exam_types = [choice[0] for choice in Exam.EXAM_TYPE_CHOICES]
    academic_years = Exam.objects.values_list("academic_year", flat=True).distinct().order_by("-academic_year")

    context = {
        "exams": exams,
        "is_admin": is_admin,
        "is_faculty": is_faculty,
        "student": student,
        "today": today,
        "total_count": total_count,
        "active_count": active_count,
        "upcoming_count": upcoming_count,
        "ongoing_count": ongoing_count,
        "completed_count": completed_count,
        "courses": courses,
        "exam_types": exam_types,
        "academic_years": academic_years,
        "filters": {
            "q": q,
            "exam_type": exam_type,
            "academic_year": academic_year,
            "course": course_id,
            "year": year,
            "semester": semester,
            "status": status,
        }
    }

    return render(request, "exams/exam_list.html", context)


# ============================================================
# EXAM DETAILS & TIMETABLE SLOTS
# ============================================================

@login_required(login_url="/accounts/login/")
def exam_detail(request, pk):
    exam = get_object_or_404(
        Exam.objects.select_related("course", "course__department", "created_by"),
        pk=pk
    )
    schedules = list(exam.schedules.select_related("subject", "invigilator").order_by("exam_date", "start_time"))

    is_admin = request.user.is_superuser or request.user.is_staff
    faculty = _get_faculty(request.user)
    is_faculty = faculty is not None
    student = Student.objects.filter(user=request.user).first()

    # Subjects faculty can manage marks for
    faculty_subjects = set(_get_faculty_assigned_subjects(faculty).values_list("id", flat=True)) if is_faculty else set()

    for s in schedules:
        s.can_manage_marks = is_admin or (is_faculty and s.subject_id in faculty_subjects)
        s.marks_entered_count = StudentExamMark.objects.filter(exam=exam, subject=s.subject).count()

    schedule_form = None
    if is_admin or is_faculty:
        if request.method == "POST" and "add_schedule" in request.POST:
            schedule_form = ExamScheduleForm(request.POST, exam=exam)
            if schedule_form.is_valid():
                sched = schedule_form.save(commit=False)
                sched.exam = exam
                sched.save()
                messages.success(request, f"Subject {sched.subject.name} added to exam schedule successfully!")
                return redirect("exam_detail", pk=exam.pk)
        else:
            schedule_form = ExamScheduleForm(exam=exam)

    context = {
        "exam": exam,
        "schedules": schedules,
        "is_admin": is_admin,
        "is_faculty": is_faculty,
        "student": student,
        "schedule_form": schedule_form,
    }
    return render(request, "exams/exam_detail.html", context)


# ============================================================
# EXAM CRUD OPERATIONS
# ============================================================

@login_required(login_url="/accounts/login/")
def exam_create(request):
    if not (request.user.is_superuser or request.user.is_staff):
        messages.error(request, "You do not have permission to create an exam.")
        return redirect("exam_list")

    if request.method == "POST":
        form = ExamForm(request.POST)
        if form.is_valid():
            exam = form.save(commit=False)
            exam.created_by = request.user
            exam.save()

            # Create notification for students of this course/year
            students = Student.objects.filter(course=exam.course, year=exam.year, user__isnull=False)
            notifs = [
                Notification(
                    recipient=st.user,
                    title=f"New Examination Scheduled: {exam.name}",
                    message=f"An exam '{exam.name}' ({exam.exam_type}) has been scheduled from {exam.start_date.strftime('%d %b %Y')} to {exam.end_date.strftime('%d %b %Y')}.",
                    link=f"/exams/{exam.pk}/"
                )
                for st in students
            ]
            if notifs:
                Notification.objects.bulk_create(notifs)

            messages.success(request, f"Exam '{exam.name}' has been created successfully!")
            return redirect("exam_detail", pk=exam.pk)
    else:
        form = ExamForm()

    return render(request, "exams/exam_form.html", {
        "form": form,
        "title": "Create New Exam",
        "action": "Create Exam",
    })


@login_required(login_url="/accounts/login/")
def exam_edit(request, pk):
    exam = get_object_or_404(Exam, pk=pk)

    if not (request.user.is_superuser or request.user.is_staff):
        messages.error(request, "You do not have permission to edit this exam.")
        return redirect("exam_list")

    if request.method == "POST":
        form = ExamForm(request.POST, instance=exam)
        if form.is_valid():
            form.save()
            messages.success(request, f"Exam '{exam.name}' updated successfully!")
            return redirect("exam_detail", pk=exam.pk)
    else:
        form = ExamForm(instance=exam)

    return render(request, "exams/exam_form.html", {
        "form": form,
        "exam": exam,
        "title": f"Edit Exam: {exam.name}",
        "action": "Update Exam",
    })


@login_required(login_url="/accounts/login/")
def exam_delete(request, pk):
    exam = get_object_or_404(Exam, pk=pk)

    if not (request.user.is_superuser or request.user.is_staff):
        messages.error(request, "You do not have permission to delete this exam.")
        return redirect("exam_list")

    if request.method == "POST":
        name = exam.name
        exam.delete()
        messages.success(request, f"Exam '{name}' has been deleted successfully.")
        return redirect("exam_list")

    return render(request, "exams/exam_confirm_delete.html", {"exam": exam})


@login_required(login_url="/accounts/login/")
def toggle_exam_status(request, pk):
    exam = get_object_or_404(Exam, pk=pk)

    if not (request.user.is_superuser or request.user.is_staff):
        return HttpResponseForbidden("Unauthorized")

    if request.method == "POST":
        exam.is_active = not exam.is_active
        exam.save(update_fields=["is_active", "updated_at"])
        status_text = "activated" if exam.is_active else "deactivated"
        messages.success(request, f"Exam '{exam.name}' is now {status_text}.")

    return redirect(request.META.get("HTTP_REFERER", "exam_list"))


@login_required(login_url="/accounts/login/")
def delete_schedule(request, schedule_id):
    schedule = get_object_or_404(ExamSchedule, pk=schedule_id)
    exam_pk = schedule.exam.pk

    if not (request.user.is_superuser or request.user.is_staff):
        return HttpResponseForbidden("Unauthorized")

    if request.method == "POST":
        subject_name = schedule.subject.name
        schedule.delete()
        messages.success(request, f"Subject schedule '{subject_name}' removed.")

    return redirect("exam_detail", pk=exam_pk)


# ============================================================
# STUDENT EXAM MARKS ENTRY & BULK MANAGEMENT
# ============================================================

@login_required(login_url="/accounts/login/")
def exam_schedule_marks_entry(request, schedule_id):
    """
    Direct marks entry interface for a specific subject slot under an exam.
    Enforces authorization: Admin or assigned Faculty only.
    """
    schedule = get_object_or_404(
        ExamSchedule.objects.select_related("exam", "subject", "exam__course"),
        pk=schedule_id
    )
    exam = schedule.exam
    subject = schedule.subject

    is_admin = request.user.is_superuser or request.user.is_staff
    faculty = _get_faculty(request.user)

    # Permission check: Admin or faculty assigned to this subject
    if not is_admin:
        if not faculty:
            return HttpResponseForbidden("You do not have permission to enter marks.")
        assigned_subjects = _get_faculty_assigned_subjects(faculty)
        if not assigned_subjects.filter(id=subject.id).exists():
            messages.error(request, "You can only manage marks for your assigned subjects.")
            return redirect("exam_detail", pk=exam.pk)

    # Retrieve all enrolled students for this course & cohort
    students = Student.objects.filter(
        course=exam.course,
        year=exam.year,
        is_approved=True
    ).order_by("roll_no", "name")

    existing_marks = {
        m.student_id: m
        for m in StudentExamMark.objects.filter(exam=exam, subject=subject)
    }

    if request.method == "POST":
        errors = []
        saved_count = 0

        for st in students:
            prefix = f"student_{st.id}_"
            marks_raw = request.POST.get(f"{prefix}marks", "").strip()
            is_absent = request.POST.get(f"{prefix}absent") == "1"
            remarks = request.POST.get(f"{prefix}remarks", "").strip()

            if is_absent:
                mark_obj, _ = StudentExamMark.objects.get_or_create(
                    student=st,
                    exam=exam,
                    subject=subject,
                    defaults={
                        "exam_schedule": schedule,
                        "max_marks": schedule.max_marks,
                        "marks_obtained": Decimal("0.00"),
                        "result_status": "Absent",
                        "remarks": remarks,
                        "entered_by": request.user,
                    }
                )
                mark_obj.marks_obtained = Decimal("0.00")
                mark_obj.result_status = "Absent"
                mark_obj.remarks = remarks
                mark_obj.save()
                saved_count += 1
                continue

            if marks_raw != "":
                try:
                    marks_val = Decimal(marks_raw)
                except Exception:
                    errors.append(f"Invalid marks value for {st.name} ({marks_raw}).")
                    continue

                if marks_val < 0:
                    errors.append(f"Marks for {st.name} cannot be negative.")
                    continue
                if marks_val > schedule.max_marks:
                    errors.append(f"Marks for {st.name} ({marks_val}) cannot exceed maximum marks ({schedule.max_marks}).")
                    continue

                mark_obj, _ = StudentExamMark.objects.get_or_create(
                    student=st,
                    exam=exam,
                    subject=subject,
                    defaults={
                        "exam_schedule": schedule,
                        "max_marks": schedule.max_marks,
                        "marks_obtained": marks_val,
                        "remarks": remarks,
                        "entered_by": request.user,
                    }
                )
                mark_obj.marks_obtained = marks_val
                mark_obj.max_marks = schedule.max_marks
                mark_obj.remarks = remarks
                mark_obj.result_status = "Pass" if (marks_val / Decimal(schedule.max_marks)) >= Decimal("0.40") else "Fail"
                mark_obj.save()
                saved_count += 1

        if errors:
            for err in errors:
                messages.error(request, err)
        if saved_count > 0:
            messages.success(request, f"Successfully saved examination marks for {saved_count} student(s) in {subject.name}.")
            return redirect("exam_schedule_marks_entry", schedule_id=schedule.id)

    # Build roster rows with prefilled values
    roster = []
    for st in students:
        mark = existing_marks.get(st.id)
        roster.append({
            "student": st,
            "mark": mark,
            "marks_obtained": mark.marks_obtained if mark else "",
            "is_absent": mark.result_status == "Absent" if mark else False,
            "remarks": mark.remarks if mark else "",
            "grade": mark.grade if mark else "",
            "result_status": mark.result_status if mark else "",
        })

    # Summary statistics
    total_entered = len(existing_marks)
    passed_count = sum(1 for m in existing_marks.values() if m.result_status == "Pass")
    failed_count = sum(1 for m in existing_marks.values() if m.result_status == "Fail")
    absent_count = sum(1 for m in existing_marks.values() if m.result_status == "Absent")

    avg_marks = None
    if existing_marks:
        present_marks = [float(m.marks_obtained) for m in existing_marks.values() if m.result_status != "Absent"]
        if present_marks:
            avg_marks = round(sum(present_marks) / len(present_marks), 2)

    context = {
        "schedule": schedule,
        "exam": exam,
        "subject": subject,
        "roster": roster,
        "total_entered": total_entered,
        "passed_count": passed_count,
        "failed_count": failed_count,
        "absent_count": absent_count,
        "avg_marks": avg_marks,
        "is_admin": is_admin,
    }
    return render(request, "exams/exam_marks_entry.html", context)


@login_required(login_url="/accounts/login/")
def exam_marks_dashboard(request):
    """
    Central marks overview:
    - Admin: All marks across all exams/subjects.
    - Faculty: Only marks for their assigned subjects.
    - Student: Redirected to student results portal.
    """
    user = request.user
    student = Student.objects.filter(user=user).first()
    is_admin = user.is_superuser or user.is_staff
    faculty = _get_faculty(user)

    if student and not (is_admin or faculty):
        return redirect("student_exam_results")

    assigned_subjects = _get_faculty_assigned_subjects(faculty) if faculty else Subject.objects.all()

    marks_qs = StudentExamMark.objects.select_related("student", "exam", "subject", "exam__course")

    if not is_admin:
        marks_qs = marks_qs.filter(subject__in=assigned_subjects)

    # Filter parameters
    exam_id = request.GET.get("exam", "").strip()
    subject_id = request.GET.get("subject", "").strip()
    result_filter = request.GET.get("result", "").strip()
    q = request.GET.get("q", "").strip()

    if exam_id:
        marks_qs = marks_qs.filter(exam_id=exam_id)
    if subject_id:
        marks_qs = marks_qs.filter(subject_id=subject_id)
    if result_filter:
        marks_qs = marks_qs.filter(result_status=result_filter)
    if q:
        marks_qs = marks_qs.filter(
            Q(student__name__icontains=q) |
            Q(student__roll_no__icontains=q) |
            Q(subject__name__icontains=q) |
            Q(exam__name__icontains=q)
        )

    marks = list(marks_qs.order_by("-updated_at")[:100])

    exams = Exam.objects.filter(is_active=True).order_by("-start_date")
    subjects = assigned_subjects if not is_admin else Subject.objects.all().select_related("course")

    # Summary numbers
    total_marks = marks_qs.count()
    pass_marks = marks_qs.filter(result_status="Pass").count()
    fail_marks = marks_qs.filter(result_status="Fail").count()
    absent_marks = marks_qs.filter(result_status="Absent").count()

    context = {
        "marks": marks,
        "exams": exams,
        "subjects": subjects,
        "is_admin": is_admin,
        "is_faculty": faculty is not None,
        "total_marks": total_marks,
        "pass_marks": pass_marks,
        "fail_marks": fail_marks,
        "absent_marks": absent_marks,
        "filters": {
            "exam": exam_id,
            "subject": subject_id,
            "result": result_filter,
            "q": q,
        }
    }
    return render(request, "exams/exam_marks_dashboard.html", context)


@login_required(login_url="/accounts/login/")
def exam_mark_edit(request, mark_id):
    mark = get_object_or_404(StudentExamMark.objects.select_related("student", "exam", "subject"), pk=mark_id)
    is_admin = request.user.is_superuser or request.user.is_staff
    faculty = _get_faculty(request.user)

    if not is_admin:
        if not faculty or not _get_faculty_assigned_subjects(faculty).filter(id=mark.subject_id).exists():
            return HttpResponseForbidden("Unauthorized to edit this mark.")

    if request.method == "POST":
        form = StudentExamMarkForm(request.POST, instance=mark)
        if form.is_valid():
            form.save()
            messages.success(request, f"Mark updated successfully for {mark.student.name}.")
            return redirect("exam_marks_dashboard")
    else:
        form = StudentExamMarkForm(instance=mark)

    return render(request, "exams/exam_mark_edit.html", {
        "form": form,
        "mark": mark,
    })


@login_required(login_url="/accounts/login/")
def exam_mark_delete(request, mark_id):
    mark = get_object_or_404(StudentExamMark, pk=mark_id)
    is_admin = request.user.is_superuser or request.user.is_staff

    if not is_admin:
        return HttpResponseForbidden("Only administrators can delete exam marks.")

    if request.method == "POST":
        student_name = mark.student.name
        subject_name = mark.subject.name
        mark.delete()
        messages.success(request, f"Exam mark for {student_name} in {subject_name} deleted.")
        return redirect("exam_marks_dashboard")

    return render(request, "exams/exam_mark_confirm_delete.html", {"mark": mark})


# ============================================================
# STUDENT EXAM RESULTS PORTAL
# ============================================================

@login_required(login_url="/accounts/login/")
def student_exam_results(request):
    """
    Dedicated Exam Results view for students (and admin viewing student portal):
    Displays subject breakdown, percentage, grade, result status,
    and overall exam performance report.
    """
    user = request.user
    student = Student.objects.filter(user=user).select_related("course", "department").first()

    # If admin is testing or student not found
    if not student:
        student_id = request.GET.get("student_id")
        if (user.is_superuser or user.is_staff) and student_id:
            student = get_object_or_404(Student, pk=student_id)
        elif user.is_superuser or user.is_staff:
            student = Student.objects.first()

    if not student:
        messages.error(request, "No student profile found for this account.")
        return redirect("exam_list")

    # Fetch all marks for this student, grouped by exam
    marks_qs = StudentExamMark.objects.filter(
        student=student
    ).select_related("exam", "subject", "exam_schedule").order_by("-exam__start_date", "subject__name")

    # Group results by exam
    exams_dict = {}
    for m in marks_qs:
        if m.exam_id not in exams_dict:
            exams_dict[m.exam_id] = {
                "exam": m.exam,
                "marks": [],
            }
        exams_dict[m.exam_id]["marks"].append(m)

    exam_reports = []
    for exam_info in exams_dict.values():
        exam = exam_info["exam"]
        marks_list = exam_info["marks"]

        total_obtained = sum(m.marks_obtained for m in marks_list)
        total_max = sum(m.max_marks for m in marks_list)
        overall_pct = round((float(total_obtained) / float(total_max)) * 100, 2) if total_max > 0 else 0.0
        all_passed = all(m.result_status == "Pass" for m in marks_list)
        overall_result = "Pass" if all_passed else "Fail"
        overall_grade, overall_gp, _ = compute_grade_and_points(overall_pct)

        exam_reports.append({
            "exam": exam,
            "marks": marks_list,
            "total_obtained": total_obtained,
            "total_max": total_max,
            "overall_percentage": overall_pct,
            "overall_result": overall_result,
            "overall_grade": overall_grade,
            "overall_grade_point": overall_gp,
            "passed_count": sum(1 for m in marks_list if m.result_status == "Pass"),
            "failed_count": sum(1 for m in marks_list if m.result_status != "Pass"),
        })

    context = {
        "student": student,
        "exam_reports": exam_reports,
    }
    return render(request, "exams/student_exam_results.html", context)
