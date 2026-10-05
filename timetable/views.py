from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.db import models
from django.utils import timezone

from faculty.models import Faculty, Subject
from students.models import Department, Course
from .models import (
    Period,
    SchoolClass,
    Timetable,
    SchoolIncharge,
    Circular,
    FacultyLeaveRequest,
    Notification,
)


# ================================================================
# HELPERS
# ================================================================

def get_faculty_for_user(request):

    faculty = Faculty.objects.filter(
        user=request.user
    ).first()

    if faculty:
        return faculty

    return Faculty.objects.filter(
        email=request.user.email
    ).first()


def get_incharge_for_user(request):

    faculty = get_faculty_for_user(request)

    if faculty is None:
        return None

    return SchoolIncharge.objects.filter(
        faculty=faculty
    ).first()


# ================================================================
# SCHOOL INCHARGE — TIMETABLE BUILDER
# ================================================================

@login_required(login_url="/accounts/login/")
def incharge_dashboard(request):

    incharge = get_incharge_for_user(request)

    if incharge is None:
        return redirect("/faculty/")

    department = incharge.department

    school_classes = SchoolClass.objects.filter(
        department=department
    ).select_related("course")

    subjects = Subject.objects.filter(
        department=department
    )

    faculty_members = Faculty.objects.filter(
        department=department
    )

    periods = Period.objects.all()

    error = None

    if request.method == "POST":

        action = request.POST.get("action")

        if action == "add_class":

            course_id = request.POST.get("course")
            year = request.POST.get("year")

            course = Course.objects.filter(
                id=course_id,
                department=department
            ).first()

            if course is None:
                error = "Invalid course selected."

            elif not year:
                error = "Please enter a year."

            else:

                SchoolClass.objects.get_or_create(
                    department=department,
                    course=course,
                    year=int(year)
                )

        elif action == "add_slot":

            school_class_id = request.POST.get("school_class")
            day_of_week = request.POST.get("day_of_week")
            period_id = request.POST.get("period")
            subject_id = request.POST.get("subject")
            faculty_id = request.POST.get("faculty")

            school_class = school_classes.filter(
                id=school_class_id
            ).first()

            subject = subjects.filter(
                id=subject_id
            ).first()

            faculty_member = faculty_members.filter(
                id=faculty_id
            ).first()

            period = periods.filter(
                id=period_id
            ).first()

            if not all([school_class, subject, faculty_member, period, day_of_week]):

                error = "Please fill in all fields."

            else:

                # Check the class isn't already booked this slot
                clash_class = Timetable.objects.filter(
                    day_of_week=day_of_week,
                    period=period,
                    school_class=school_class
                ).exclude(
                    id=request.POST.get("editing_id") or 0
                ).first()

                # Check the faculty isn't already booked this slot
                clash_faculty = Timetable.objects.filter(
                    day_of_week=day_of_week,
                    period=period,
                    faculty=faculty_member
                ).exclude(
                    id=request.POST.get("editing_id") or 0
                ).first()

                if subject.faculty_id != faculty_member.id:

                    error = (
                        f"{subject.name} is assigned to "
                        f"{subject.faculty.name}, so select that faculty member."
                    )

                elif clash_class:

                    error = (
                        f"{school_class} already has a class "
                        f"in that period."
                    )

                elif clash_faculty:

                    error = (
                        f"{faculty_member.name} is already teaching "
                        f"another class in that period."
                    )

                else:

                    Timetable.objects.update_or_create(
                        day_of_week=day_of_week,
                        period=period,
                        school_class=school_class,
                        defaults={
                            "subject": subject,
                            "faculty": faculty_member,
                        }
                    )

    timetable_slots = Timetable.objects.filter(
        school_class__department=department
    ).select_related(
        "period",
        "school_class",
        "subject",
        "faculty"
    )

    return render(
        request,
        "timetable/incharge_dashboard.html",
        {
            "incharge": incharge,
            "department": department,
            "school_classes": school_classes,
            "subjects": subjects,
            "faculty_members": faculty_members,
            "periods": periods,
            "timetable_slots": timetable_slots,
            "courses": Course.objects.filter(department=department),
            "error": error,
        }
    )


@login_required(login_url="/accounts/login/")
def delete_slot(request, slot_id):

    incharge = get_incharge_for_user(request)

    if incharge is None:
        return redirect("/faculty/")

    Timetable.objects.filter(
        id=slot_id,
        school_class__department=incharge.department
    ).delete()

    return redirect("/timetable/incharge/")


# ================================================================
# FACULTY — VIEW MY TIMETABLE
# ================================================================

@login_required(login_url="/accounts/login/")
def my_timetable(request):

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

    return render(
        request,
        "timetable/my_timetable.html",
        {
            "faculty": faculty,
            "slots": slots,
        }
    )


# ================================================================
# CIRCULARS
# ================================================================

@login_required(login_url="/accounts/login/")
def post_circular(request):

    if not request.user.is_superuser:
        return redirect("/accounts/login/")

    if request.method == "POST":

        title = request.POST.get("title", "").strip()
        message = request.POST.get("message", "").strip()
        audience = request.POST.get("audience", "ALL")
        target_department = request.POST.get("target_department") or None
        target_course = request.POST.get("target_course") or None
        target_year = request.POST.get("target_year") or None

        if title and message:

            circular = Circular.objects.create(
                title=title,
                message=message,
                audience=audience,
                posted_by=request.user,
                target_department_id=target_department if audience != "ALL" else None,
                target_course_id=target_course if audience != "ALL" else None,
                target_year=target_year if audience != "ALL" else None,
            )

            from students.models import Student
            recipients = []
            if audience in ("ALL", "STUDENT"):
                qs = Student.objects.filter(is_approved=True, is_active=True, user__isnull=False)
                if target_department:
                    qs = qs.filter(department_id=target_department)
                if target_course:
                    qs = qs.filter(course_id=target_course)
                if target_year:
                    qs = qs.filter(year=target_year)
                recipients.extend(qs.values_list("user_id", flat=True))
            if audience in ("ALL", "FACULTY"):
                qs = Faculty.objects.filter(is_approved=True, is_active=True, user__isnull=False)
                if target_department:
                    qs = qs.filter(department_id=target_department)
                recipients.extend(qs.values_list("user_id", flat=True))
            Notification.objects.bulk_create([
                Notification(recipient_id=user_id, title=title, message=message, link="/timetable/circulars/")
                for user_id in set(recipients)
            ])

    return redirect("/accounts/admin-dashboard/?tab=circulars")


@login_required(login_url="/accounts/login/")
def delete_circular(request, circular_id):

    if not request.user.is_superuser:
        return redirect("/accounts/login/")

    Circular.objects.filter(id=circular_id).delete()

    return redirect("/accounts/admin-dashboard/?tab=circulars")


@login_required(login_url="/accounts/login/")
def circular_list(request):

    from students.models import Student

    is_student = Student.objects.filter(user=request.user).exists()
    is_faculty = Faculty.objects.filter(user=request.user).exists()

    circulars = Circular.objects.all()

    if is_student and not request.user.is_superuser:
        student = Student.objects.filter(user=request.user).select_related("department", "course").first()
        circulars = circulars.filter(audience__in=["ALL", "STUDENT"]).filter(
            models.Q(audience="ALL")
            | models.Q(target_department__isnull=True, target_course__isnull=True, target_year__isnull=True)
            | models.Q(target_department=student.department, target_course__isnull=True, target_year__isnull=True)
            | models.Q(target_course=student.course, target_year__isnull=True)
            | models.Q(target_course=student.course, target_year=student.year)
        ) if student else circulars.none()

    elif is_faculty and not request.user.is_superuser:
        faculty = Faculty.objects.filter(user=request.user).first() or Faculty.objects.filter(email=request.user.email).first()
        circulars = circulars.filter(audience__in=["ALL", "FACULTY"]).filter(
            models.Q(audience="ALL")
            | models.Q(target_department__isnull=True, target_course__isnull=True, target_year__isnull=True)
            | models.Q(target_department=faculty.department)
        ) if faculty else circulars.none()

    return render(
        request,
        "timetable/circular_list.html",
        {
            "circulars": circulars,
        }
    )


# ================================================================
# FACULTY LEAVE — SCHOOL INCHARGE REVIEW
# ================================================================

@login_required(login_url="/accounts/login/")
def incharge_leaves(request):

    incharge = get_incharge_for_user(request)
    if incharge is None:
        return redirect("/faculty/")

    requests = FacultyLeaveRequest.objects.filter(
        department=incharge.department
    ).select_related("faculty", "reviewed_by")

    from student_leave.models import StudentLeaveRequest, StudentLeaveHistory

    student_leaves_qs = StudentLeaveRequest.objects.filter(
        student__department=incharge.department
    ).select_related("student__course", "student__department")
    student_pending_leaves = student_leaves_qs.filter(status=StudentLeaveRequest.STATUS_FACULTY_APPROVED)
    student_approved_count = student_leaves_qs.filter(
        status__in=[StudentLeaveRequest.STATUS_INCHARGE_APPROVED, StudentLeaveRequest.STATUS_ADMIN_APPROVED]
    ).count()
    student_rejected_count = student_leaves_qs.filter(status=StudentLeaveRequest.STATUS_INCHARGE_REJECTED).count()

    if request.method == "POST":
        target = request.POST.get("target")

        if target == "student_leave":
            student_leave_id = request.POST.get("student_leave_id")
            s_action = request.POST.get("action")
            s_remarks = request.POST.get("comment", "").strip()

            s_leave = student_leaves_qs.filter(
                id=student_leave_id,
                status=StudentLeaveRequest.STATUS_FACULTY_APPROVED,
            ).first()

            if s_leave and s_action in ("approve", "reject"):
                prev_status = s_leave.status
                if s_action == "approve":
                    s_leave.status = StudentLeaveRequest.STATUS_INCHARGE_APPROVED
                    s_leave.incharge_remarks = s_remarks
                    s_leave.save()

                    StudentLeaveHistory.objects.create(
                        leave_request=s_leave,
                        action="Incharge Approved",
                        previous_status=prev_status,
                        new_status=StudentLeaveRequest.STATUS_INCHARGE_APPROVED,
                        action_taken_by=request.user,
                        remarks=s_remarks,
                    )

                    if s_leave.student.user:
                        Notification.objects.create(
                            recipient=s_leave.student.user,
                            title="Leave Approved by School Incharge",
                            message=f"Your leave request ({s_leave.from_date} to {s_leave.to_date}) was approved by School Incharge and forwarded to Administrator.",
                            link=f"/leaves/{s_leave.id}/",
                        )
                else:
                    s_leave.status = StudentLeaveRequest.STATUS_INCHARGE_REJECTED
                    s_leave.incharge_remarks = s_remarks
                    s_leave.approved_rejected_date = timezone.now()
                    s_leave.approved_rejected_by = request.user
                    s_leave.save()

                    StudentLeaveHistory.objects.create(
                        leave_request=s_leave,
                        action="Incharge Rejected",
                        previous_status=prev_status,
                        new_status=StudentLeaveRequest.STATUS_INCHARGE_REJECTED,
                        action_taken_by=request.user,
                        remarks=s_remarks,
                    )

                    if s_leave.student.user:
                        Notification.objects.create(
                            recipient=s_leave.student.user,
                            title="Leave Rejected by School Incharge",
                            message=f"Your leave request was rejected by School Incharge. Remarks: {s_remarks}",
                            link=f"/leaves/{s_leave.id}/",
                        )

            return redirect("/timetable/incharge-leaves/")

        leave_id = request.POST.get("leave_id")
        action = request.POST.get("action")
        comment = request.POST.get("comment", "").strip()

        leave = requests.filter(id=leave_id, status="PENDING").first()

        if leave is not None and action in ("approve", "reject"):
            leave.status = "APPROVED" if action == "approve" else "REJECTED"
            leave.incharge_comment = comment
            leave.reviewed_by = incharge.faculty
            leave.reviewed_at = timezone.now()
            # Only approved requests are forwarded to the administrator.
            leave.forwarded_to_admin = action == "approve"
            leave.admin_seen = False
            leave.save()

            if action == "approve" and leave.faculty.user_id:
                Notification.objects.create(
                    recipient=leave.faculty.user,
                    title="Leave approved",
                    message=f"Your {leave.get_leave_type_display()} request was approved by the School Incharge and forwarded to Admin.",
                    link="/faculty/leave-request/",
                )

        return redirect("/timetable/incharge-leaves/")

    return render(request, "timetable/incharge_leaves.html", {
        "incharge": incharge,
        "requests": requests,
        "student_pending_leaves": student_pending_leaves,
        "student_pending_count": student_pending_leaves.count(),
        "student_approved_count": student_approved_count,
        "student_rejected_count": student_rejected_count,
    })


@login_required(login_url="/accounts/login/")
def notifications(request):
    items = Notification.objects.filter(recipient=request.user)
    if request.method == "POST":
        Notification.objects.filter(recipient=request.user, is_read=False).update(is_read=True)
        return redirect("/timetable/notifications/")
    return render(request, "timetable/notifications.html", {"notifications": items})
