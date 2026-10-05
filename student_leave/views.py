import os
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponseForbidden, FileResponse, Http404
from django.utils import timezone
from django.db.models import Q, Count
from django.contrib.auth.models import User

from .models import StudentLeaveRequest, StudentLeaveHistory
from .forms import StudentLeaveApplyForm, LeaveActionForm
from students.models import Student, Department, Course
from faculty.models import Faculty, Subject
from timetable.models import Notification, SchoolIncharge, Timetable


def notify_user(user, title, message, link=""):
    """Safely create a notification for a user using the existing model."""
    if user and user.is_authenticated:
        try:
            Notification.objects.create(
                recipient=user,
                title=title,
                message=message,
                link=link or "/leaves/",
            )
        except Exception:
            pass


def get_authorized_faculties_for_student(student):
    """
    Returns a QuerySet of Faculty members who teach this student's course & year
    or are part of the student's department.
    """
    if not student:
        return Faculty.objects.none()

    sub_faculty_ids = Subject.objects.filter(
        course=student.course,
        year=student.year,
    ).values_list("faculty_id", flat=True)

    tt_faculty_ids = Timetable.objects.filter(
        school_class__course=student.course,
        school_class__year=student.year,
    ).values_list("faculty_id", flat=True)

    combined_ids = set(list(sub_faculty_ids) + list(tt_faculty_ids))

    if combined_ids:
        return Faculty.objects.filter(Q(id__in=combined_ids) | Q(department=student.department)).distinct()
    return Faculty.objects.filter(department=student.department).distinct()


def is_faculty_authorized_for_student(faculty, student):
    """Check if a specific faculty member is authorized to review this student's leave."""
    if not faculty or not student:
        return False
    # Check course & year teaching
    teaches_student = Subject.objects.filter(
        faculty=faculty,
        course=student.course,
        year=student.year,
    ).exists() or Timetable.objects.filter(
        faculty=faculty,
        school_class__course=student.course,
        school_class__year=student.year,
    ).exists()
    # Or in the same department
    return teaches_student or (faculty.department_id == student.department_id)


def get_current_user_profile(user):
    """
    Returns a dict with resolved role information for the logged-in user.
    """
    student = Student.objects.filter(user=user).select_related("course", "department").first()
    faculty = None
    is_incharge = None
    incharge_department = None

    if not student:
        faculty = (
            Faculty.objects.filter(user=user).select_related("department").first()
            or Faculty.objects.filter(email=user.email).select_related("department").first()
        )
        if faculty:
            si = SchoolIncharge.objects.filter(faculty=faculty).select_related("department").first()
            if si:
                is_incharge = si
                incharge_department = si.department

    is_admin = (user.is_superuser or user.is_staff) and not student

    return {
        "student": student,
        "faculty": faculty,
        "is_incharge": is_incharge,
        "incharge_department": incharge_department,
        "is_admin": is_admin,
    }


# ============================================================
# 1. STUDENT LEAVE LIST / DASHBOARD DISPATCHER
# ============================================================

@login_required(login_url="/accounts/login/")
def leave_list(request):
    """
    Shows the student's leave requests with status badges, filters, and statistics.
    If the user is not a student, dispatches to their respective review list.
    """
    ctx_role = get_current_user_profile(request.user)

    if ctx_role["is_admin"]:
        return redirect("admin_leave_list")
    elif ctx_role["is_incharge"]:
        # If incharge, can also view faculty review or incharge review
        # But if they clicked leaves, let's give them faculty or incharge view
        pass
    elif ctx_role["faculty"]:
        return redirect("faculty_leave_list")

    student = ctx_role["student"]
    if not student:
        messages.error(request, "No student profile found for this account.")
        return redirect("/accounts/login/")

    leaves_qs = StudentLeaveRequest.objects.filter(student=student).order_by("-applied_date")

    # Filters
    status_filter = request.GET.get("status", "").strip()
    type_filter = request.GET.get("type", "").strip()

    if status_filter:
        leaves_qs = leaves_qs.filter(status=status_filter)
    if type_filter:
        leaves_qs = leaves_qs.filter(leave_type=type_filter)

    all_student_leaves = StudentLeaveRequest.objects.filter(student=student)
    total_count = all_student_leaves.count()
    pending_count = all_student_leaves.filter(
        status__in=[
            StudentLeaveRequest.STATUS_PENDING,
            StudentLeaveRequest.STATUS_FACULTY_APPROVED,
            StudentLeaveRequest.STATUS_INCHARGE_APPROVED,
        ]
    ).count()
    approved_count = all_student_leaves.filter(status=StudentLeaveRequest.STATUS_ADMIN_APPROVED).count()
    rejected_count = all_student_leaves.filter(
        status__in=[
            StudentLeaveRequest.STATUS_FACULTY_REJECTED,
            StudentLeaveRequest.STATUS_INCHARGE_REJECTED,
            StudentLeaveRequest.STATUS_ADMIN_REJECTED,
        ]
    ).count()

    return render(
        request,
        "student_leave/leave_list.html",
        {
            "leaves": leaves_qs,
            "student": student,
            "total_count": total_count,
            "pending_count": pending_count,
            "approved_count": approved_count,
            "rejected_count": rejected_count,
            "status_filter": status_filter,
            "type_filter": type_filter,
            "leave_types": StudentLeaveRequest.LEAVE_TYPE_CHOICES,
            "status_choices": StudentLeaveRequest.STATUS_CHOICES,
        },
    )


# ============================================================
# 2. APPLY FOR LEAVE (STUDENT)
# ============================================================

@login_required(login_url="/accounts/login/")
def apply_leave(request):
    """
    Allows a student to submit a new leave request.
    Validates date boundaries, past-date rules, and overlapping requests.
    """
    ctx_role = get_current_user_profile(request.user)
    student = ctx_role["student"]

    if not student:
        messages.error(request, "Only students can apply for student leaves.")
        return redirect("leave_list")

    if request.method == "POST":
        form = StudentLeaveApplyForm(request.POST, request.FILES, student=student)
        if form.is_valid():
            leave = form.save(commit=False)
            leave.student = student
            leave.status = StudentLeaveRequest.STATUS_PENDING
            leave.save()

            # Record audit history
            StudentLeaveHistory.objects.create(
                leave_request=leave,
                action="Submitted",
                previous_status="",
                new_status=StudentLeaveRequest.STATUS_PENDING,
                action_taken_by=request.user,
                remarks=leave.student_remarks or "Leave application submitted by student.",
            )

            # Notify authorized faculty
            authorized_faculties = get_authorized_faculties_for_student(student)
            for fac in authorized_faculties:
                if fac.user:
                    notify_user(
                        fac.user,
                        title="New Student Leave Request",
                        message=f"{student.name} ({student.roll_no}) applied for {leave.leave_type} ({leave.from_date} to {leave.to_date}).",
                        link=f"/leaves/{leave.pk}/",
                    )

            messages.success(request, f"Leave application submitted successfully for {leave.number_of_days} day(s).")
            return redirect("leave_detail", pk=leave.pk)
    else:
        form = StudentLeaveApplyForm(student=student)

    return render(
        request,
        "student_leave/apply_leave.html",
        {
            "form": form,
            "student": student,
        },
    )


# ============================================================
# 3. LEAVE DETAIL & AUDIT TIMELINE
# ============================================================

@login_required(login_url="/accounts/login/")
def leave_detail(request, pk):
    """
    Detailed view of a leave request:
    - Displays full student & academic profile
    - Shows leave dates, reason, document attachment
    - Complete visual approval stepper
    - Chronological audit history log
    - Remarks from each approval level
    - Permission-checked action forms for Student, Faculty, Incharge, and Admin
    """
    leave = get_object_or_404(
        StudentLeaveRequest.objects.select_related(
            "student__user",
            "student__course",
            "student__department",
            "approved_rejected_by",
        ),
        pk=pk,
    )

    ctx_role = get_current_user_profile(request.user)
    student = ctx_role["student"]
    faculty = ctx_role["faculty"]
    is_incharge = ctx_role["is_incharge"]
    is_admin = ctx_role["is_admin"]

    # Security check: User must be either the student, authorized faculty, incharge of the school, or admin
    is_owner = student and (leave.student == student)
    is_authorized_faculty = faculty and is_faculty_authorized_for_student(faculty, leave.student)
    is_authorized_incharge = is_incharge and (is_incharge.department_id == leave.student.department_id)

    if not (is_owner or is_admin or is_authorized_incharge or is_authorized_faculty):
        return HttpResponseForbidden("You do not have permission to view this leave request.")

    # Permissions for actions
    can_cancel = is_owner and leave.can_student_cancel
    can_faculty_act = is_authorized_faculty and (leave.status == StudentLeaveRequest.STATUS_PENDING)
    can_incharge_act = is_authorized_incharge and (leave.status == StudentLeaveRequest.STATUS_FACULTY_APPROVED)
    can_admin_act = is_admin and not leave.is_final_decision

    history_records = leave.history.select_related("action_taken_by").all().order_by("timestamp")
    action_form = LeaveActionForm()

    return render(
        request,
        "student_leave/leave_detail.html",
        {
            "leave": leave,
            "student": leave.student,
            "history_records": history_records,
            "can_cancel": can_cancel,
            "can_faculty_act": can_faculty_act,
            "can_incharge_act": can_incharge_act,
            "can_admin_act": can_admin_act,
            "is_owner": is_owner,
            "is_admin": is_admin,
            "action_form": action_form,
        },
    )


# ============================================================
# 4. CANCEL LEAVE (STUDENT)
# ============================================================

@login_required(login_url="/accounts/login/")
def cancel_leave(request, pk):
    """Allows student to cancel a pending leave request."""
    if request.method != "POST":
        return redirect("leave_detail", pk=pk)

    leave = get_object_or_404(StudentLeaveRequest, pk=pk)
    ctx_role = get_current_user_profile(request.user)

    if not (ctx_role["student"] and leave.student == ctx_role["student"]):
        return HttpResponseForbidden("You can only cancel your own leave requests.")

    if not leave.can_student_cancel:
        messages.error(request, "This leave request cannot be cancelled in its current state.")
        return redirect("leave_detail", pk=pk)

    prev_status = leave.status
    leave.status = StudentLeaveRequest.STATUS_CANCELLED
    leave.save()

    StudentLeaveHistory.objects.create(
        leave_request=leave,
        action="Cancelled",
        previous_status=prev_status,
        new_status=StudentLeaveRequest.STATUS_CANCELLED,
        action_taken_by=request.user,
        remarks="Cancelled by student.",
    )

    # Notify faculty
    for fac in get_authorized_faculties_for_student(leave.student):
        if fac.user:
            notify_user(
                fac.user,
                title="Leave Request Cancelled",
                message=f"{leave.student.name} cancelled their leave request for {leave.from_date} to {leave.to_date}.",
                link=f"/leaves/{leave.pk}/",
            )

    messages.info(request, "Leave request has been cancelled.")
    return redirect("leave_detail", pk=pk)


# ============================================================
# 5. FACULTY REVIEW ACTION
# ============================================================

@login_required(login_url="/accounts/login/")
def faculty_review_action(request, pk):
    """Faculty reviews pending leave request and approves or rejects."""
    if request.method != "POST":
        return redirect("leave_detail", pk=pk)

    leave = get_object_or_404(StudentLeaveRequest, pk=pk)
    ctx_role = get_current_user_profile(request.user)
    faculty = ctx_role["faculty"]
    is_admin = ctx_role["is_admin"]

    if not (is_admin or (faculty and is_faculty_authorized_for_student(faculty, leave.student))):
        return HttpResponseForbidden("You are not authorized to review this student's leave.")

    if leave.status != StudentLeaveRequest.STATUS_PENDING:
        messages.error(request, "This request is not in Pending status.")
        return redirect("leave_detail", pk=pk)

    action = request.POST.get("action")
    remarks = request.POST.get("remarks", "").strip()

    prev_status = leave.status
    if action == "approve":
        new_status = StudentLeaveRequest.STATUS_FACULTY_APPROVED
        action_name = "Faculty Approved"
        leave.faculty_remarks = remarks
        leave.status = new_status
        leave.save()

        # Notify student
        if leave.student.user:
            notify_user(
                leave.student.user,
                title="Leave Approved by Faculty",
                message=f"Your leave request ({leave.from_date} to {leave.to_date}) was approved by Faculty and forwarded to School Incharge.",
                link=f"/leaves/{leave.pk}/",
            )

        # Notify School Incharge
        incharge = SchoolIncharge.objects.filter(department=leave.student.department).select_related("faculty__user").first()
        if incharge and incharge.faculty and incharge.faculty.user:
            notify_user(
                incharge.faculty.user,
                title="Leave Request Awaiting Incharge Review",
                message=f"{leave.student.name}'s leave request was approved by Faculty and awaits your decision.",
                link=f"/leaves/{leave.pk}/",
            )

        messages.success(request, f"Leave request for {leave.student.name} approved and forwarded to School Incharge.")

    elif action == "reject":
        new_status = StudentLeaveRequest.STATUS_FACULTY_REJECTED
        action_name = "Faculty Rejected"
        leave.faculty_remarks = remarks
        leave.status = new_status
        leave.approved_rejected_date = timezone.now()
        leave.approved_rejected_by = request.user
        leave.save()

        # Notify student
        if leave.student.user:
            notify_user(
                leave.student.user,
                title="Leave Rejected by Faculty",
                message=f"Your leave request ({leave.from_date} to {leave.to_date}) was rejected by Faculty. Remarks: {remarks}",
                link=f"/leaves/{leave.pk}/",
            )

        messages.warning(request, f"Leave request for {leave.student.name} has been rejected.")
    else:
        messages.error(request, "Invalid action.")
        return redirect("leave_detail", pk=pk)

    StudentLeaveHistory.objects.create(
        leave_request=leave,
        action=action_name,
        previous_status=prev_status,
        new_status=new_status,
        action_taken_by=request.user,
        remarks=remarks,
    )

    return redirect("leave_detail", pk=pk)


# ============================================================
# 6. SCHOOL INCHARGE REVIEW ACTION
# ============================================================

@login_required(login_url="/accounts/login/")
def incharge_review_action(request, pk):
    """School Incharge reviews Faculty Approved request and approves or rejects."""
    if request.method != "POST":
        return redirect("leave_detail", pk=pk)

    leave = get_object_or_404(StudentLeaveRequest, pk=pk)
    ctx_role = get_current_user_profile(request.user)
    is_incharge = ctx_role["is_incharge"]
    is_admin = ctx_role["is_admin"]

    if not (is_admin or (is_incharge and is_incharge.department_id == leave.student.department_id)):
        return HttpResponseForbidden("You are not the designated School Incharge for this student's department.")

    if leave.status != StudentLeaveRequest.STATUS_FACULTY_APPROVED:
        messages.error(request, "This request is not awaiting School Incharge approval.")
        return redirect("leave_detail", pk=pk)

    action = request.POST.get("action")
    remarks = request.POST.get("remarks", "").strip()

    prev_status = leave.status
    if action == "approve":
        new_status = StudentLeaveRequest.STATUS_INCHARGE_APPROVED
        action_name = "Incharge Approved"
        leave.incharge_remarks = remarks
        leave.status = new_status
        leave.save()

        # Notify student
        if leave.student.user:
            notify_user(
                leave.student.user,
                title="Leave Approved by School Incharge",
                message=f"Your leave request ({leave.from_date} to {leave.to_date}) was approved by School Incharge and forwarded to Administrator.",
                link=f"/leaves/{leave.pk}/",
            )

        # Notify Administrators
        for admin_user in User.objects.filter(Q(is_superuser=True) | Q(is_staff=True)).distinct():
            notify_user(
                admin_user,
                title="Leave Request Awaiting Admin Approval",
                message=f"{leave.student.name} ({leave.student.roll_no}) leave approved by Incharge; awaits final Admin approval.",
                link=f"/leaves/{leave.pk}/",
            )

        messages.success(request, f"Leave request approved and forwarded to Administrator for final authorization.")

    elif action == "reject":
        new_status = StudentLeaveRequest.STATUS_INCHARGE_REJECTED
        action_name = "Incharge Rejected"
        leave.incharge_remarks = remarks
        leave.status = new_status
        leave.approved_rejected_date = timezone.now()
        leave.approved_rejected_by = request.user
        leave.save()

        if leave.student.user:
            notify_user(
                leave.student.user,
                title="Leave Rejected by School Incharge",
                message=f"Your leave request ({leave.from_date} to {leave.to_date}) was rejected by School Incharge. Remarks: {remarks}",
                link=f"/leaves/{leave.pk}/",
            )

        messages.warning(request, f"Leave request for {leave.student.name} rejected by School Incharge.")
    else:
        messages.error(request, "Invalid action.")
        return redirect("leave_detail", pk=pk)

    StudentLeaveHistory.objects.create(
        leave_request=leave,
        action=action_name,
        previous_status=prev_status,
        new_status=new_status,
        action_taken_by=request.user,
        remarks=remarks,
    )

    return redirect("leave_detail", pk=pk)


# ============================================================
# 7. ADMIN REVIEW ACTION (FINAL STAGE)
# ============================================================

@login_required(login_url="/accounts/login/")
def admin_review_action(request, pk):
    """Administrator conducts final approval or rejection."""
    if request.method != "POST":
        return redirect("leave_detail", pk=pk)

    leave = get_object_or_404(StudentLeaveRequest, pk=pk)
    ctx_role = get_current_user_profile(request.user)

    if not ctx_role["is_admin"]:
        return HttpResponseForbidden("Only administrators can perform final leave authorization.")

    if leave.is_final_decision:
        messages.error(request, "This leave request has already reached a final status.")
        return redirect("leave_detail", pk=pk)

    action = request.POST.get("action")
    remarks = request.POST.get("remarks", "").strip()

    prev_status = leave.status
    if action == "approve":
        new_status = StudentLeaveRequest.STATUS_ADMIN_APPROVED
        action_name = "Admin Approved"
        leave.admin_remarks = remarks
        leave.status = new_status
        leave.approved_rejected_date = timezone.now()
        leave.approved_rejected_by = request.user
        leave.save()

        if leave.student.user:
            notify_user(
                leave.student.user,
                title="Final Leave Authorization: APPROVED",
                message=f"Congratulations! Your leave request for {leave.from_date} to {leave.to_date} has received final Admin Approval.",
                link=f"/leaves/{leave.pk}/",
            )

        messages.success(request, f"Leave request for {leave.student.name} has been given final Admin Approval.")

    elif action == "reject":
        new_status = StudentLeaveRequest.STATUS_ADMIN_REJECTED
        action_name = "Admin Rejected"
        leave.admin_remarks = remarks
        leave.status = new_status
        leave.approved_rejected_date = timezone.now()
        leave.approved_rejected_by = request.user
        leave.save()

        if leave.student.user:
            notify_user(
                leave.student.user,
                title="Final Leave Authorization: REJECTED",
                message=f"Your leave request ({leave.from_date} to {leave.to_date}) was rejected by Administrator. Remarks: {remarks}",
                link=f"/leaves/{leave.pk}/",
            )

        messages.warning(request, f"Leave request for {leave.student.name} has been rejected by Administrator.")
    else:
        messages.error(request, "Invalid action.")
        return redirect("leave_detail", pk=pk)

    StudentLeaveHistory.objects.create(
        leave_request=leave,
        action=action_name,
        previous_status=prev_status,
        new_status=new_status,
        action_taken_by=request.user,
        remarks=remarks,
    )

    return redirect("leave_detail", pk=pk)


# ============================================================
# 8. FACULTY REVIEW DASHBOARD
# ============================================================

@login_required(login_url="/accounts/login/")
def faculty_leave_list(request):
    """
    Faculty dashboard view for student leave requests:
    - Pending student leave requests
    - Approved requests
    - Rejected requests
    - Quick approve/reject actions
    """
    ctx_role = get_current_user_profile(request.user)
    faculty = ctx_role["faculty"]
    is_admin = ctx_role["is_admin"]

    if not (faculty or is_admin):
        return redirect("leave_list")

    # Filter students this faculty is authorized for
    if is_admin:
        base_qs = StudentLeaveRequest.objects.all()
    else:
        # Students in faculty's department or taught by faculty
        taught_courses = Subject.objects.filter(faculty=faculty).values_list("course_id", flat=True)
        base_qs = StudentLeaveRequest.objects.filter(
            Q(student__department=faculty.department) | Q(student__course_id__in=taught_courses)
        ).distinct()

    base_qs = base_qs.select_related("student__course", "student__department").order_by("-applied_date")

    pending_qs = base_qs.filter(status=StudentLeaveRequest.STATUS_PENDING)
    approved_qs = base_qs.filter(
        status__in=[
            StudentLeaveRequest.STATUS_FACULTY_APPROVED,
            StudentLeaveRequest.STATUS_INCHARGE_APPROVED,
            StudentLeaveRequest.STATUS_ADMIN_APPROVED,
        ]
    )
    rejected_qs = base_qs.filter(status=StudentLeaveRequest.STATUS_FACULTY_REJECTED)

    tab = request.GET.get("tab", "pending")
    search_q = request.GET.get("q", "").strip()

    if search_q:
        base_qs = base_qs.filter(
            Q(student__name__icontains=search_q) | Q(student__roll_no__icontains=search_q)
        )
        pending_qs = pending_qs.filter(
            Q(student__name__icontains=search_q) | Q(student__roll_no__icontains=search_q)
        )
        approved_qs = approved_qs.filter(
            Q(student__name__icontains=search_q) | Q(student__roll_no__icontains=search_q)
        )
        rejected_qs = rejected_qs.filter(
            Q(student__name__icontains=search_q) | Q(student__roll_no__icontains=search_q)
        )

    return render(
        request,
        "student_leave/faculty_leave_list.html",
        {
            "pending_leaves": pending_qs,
            "approved_leaves": approved_qs,
            "rejected_leaves": rejected_qs,
            "pending_count": pending_qs.count(),
            "approved_count": approved_qs.count(),
            "rejected_count": rejected_qs.count(),
            "tab": tab,
            "search_q": search_q,
            "faculty": faculty,
        },
    )


# ============================================================
# 9. SCHOOL INCHARGE REVIEW DASHBOARD
# ============================================================

@login_required(login_url="/accounts/login/")
def incharge_leave_list(request):
    """
    School Incharge dashboard for student leaves:
    - Pending requests (Faculty Approved requests for their School)
    - Approved/Rejected statistics
    - Direct review actions
    """
    ctx_role = get_current_user_profile(request.user)
    is_incharge = ctx_role["is_incharge"]
    is_admin = ctx_role["is_admin"]

    if not (is_incharge or is_admin):
        return HttpResponseForbidden("You are not registered as a School Incharge.")

    if is_admin and not is_incharge:
        dept = Department.objects.first()
    else:
        dept = is_incharge.department

    base_qs = StudentLeaveRequest.objects.filter(student__department=dept).select_related(
        "student__course", "student__department"
    ).order_by("-applied_date")

    pending_incharge_qs = base_qs.filter(status=StudentLeaveRequest.STATUS_FACULTY_APPROVED)
    all_pending_qs = base_qs.filter(status=StudentLeaveRequest.STATUS_PENDING)
    approved_qs = base_qs.filter(
        status__in=[StudentLeaveRequest.STATUS_INCHARGE_APPROVED, StudentLeaveRequest.STATUS_ADMIN_APPROVED]
    )
    rejected_qs = base_qs.filter(status=StudentLeaveRequest.STATUS_INCHARGE_REJECTED)

    return render(
        request,
        "student_leave/incharge_leave_list.html",
        {
            "department": dept,
            "pending_incharge_leaves": pending_incharge_qs,
            "all_pending_leaves": all_pending_qs,
            "approved_leaves": approved_qs,
            "rejected_leaves": rejected_qs,
            "pending_count": pending_incharge_qs.count(),
            "faculty_pending_count": all_pending_qs.count(),
            "approved_count": approved_qs.count(),
            "rejected_count": rejected_qs.count(),
        },
    )


# ============================================================
# 10. ADMIN ALL LEAVES MANAGEMENT & FILTERS
# ============================================================

@login_required(login_url="/accounts/login/")
def admin_leave_list(request):
    """
    Admin central oversight:
    - View all leave requests
    - Filters: school, course, year, leave_type, status, search
    - Direct authorization links
    - High-level KPIs
    """
    ctx_role = get_current_user_profile(request.user)
    if not ctx_role["is_admin"]:
        return HttpResponseForbidden("Administrative privileges required.")

    leaves_qs = StudentLeaveRequest.objects.select_related(
        "student__course", "student__department"
    ).order_by("-applied_date")

    # Metrics
    total_count = leaves_qs.count()
    pending_admin_count = leaves_qs.filter(status=StudentLeaveRequest.STATUS_INCHARGE_APPROVED).count()
    total_pending_count = leaves_qs.filter(
        status__in=[
            StudentLeaveRequest.STATUS_PENDING,
            StudentLeaveRequest.STATUS_FACULTY_APPROVED,
            StudentLeaveRequest.STATUS_INCHARGE_APPROVED,
        ]
    ).count()
    approved_count = leaves_qs.filter(status=StudentLeaveRequest.STATUS_ADMIN_APPROVED).count()
    rejected_count = leaves_qs.filter(
        status__in=[
            StudentLeaveRequest.STATUS_FACULTY_REJECTED,
            StudentLeaveRequest.STATUS_INCHARGE_REJECTED,
            StudentLeaveRequest.STATUS_ADMIN_REJECTED,
        ]
    ).count()

    # Filter parameters
    school_id = request.GET.get("school", "").strip()
    course_id = request.GET.get("course", "").strip()
    year_val = request.GET.get("year", "").strip()
    leave_type = request.GET.get("leave_type", "").strip()
    status_val = request.GET.get("status", "").strip()
    search_q = request.GET.get("q", "").strip()

    if school_id:
        leaves_qs = leaves_qs.filter(student__department_id=school_id)
    if course_id:
        leaves_qs = leaves_qs.filter(student__course_id=course_id)
    if year_val:
        leaves_qs = leaves_qs.filter(student__year=year_val)
    if leave_type:
        leaves_qs = leaves_qs.filter(leave_type=leave_type)
    if status_val:
        leaves_qs = leaves_qs.filter(status=status_val)
    if search_q:
        leaves_qs = leaves_qs.filter(
            Q(student__name__icontains=search_q)
            | Q(student__roll_no__icontains=search_q)
            | Q(reason__icontains=search_q)
        )

    schools = Department.objects.all().order_by("name")
    courses = Course.objects.all().order_by("name")

    return render(
        request,
        "student_leave/admin_leave_list.html",
        {
            "leaves": leaves_qs,
            "total_count": total_count,
            "pending_admin_count": pending_admin_count,
            "total_pending_count": total_pending_count,
            "approved_count": approved_count,
            "rejected_count": rejected_count,
            "schools": schools,
            "courses": courses,
            "leave_types": StudentLeaveRequest.LEAVE_TYPE_CHOICES,
            "status_choices": StudentLeaveRequest.STATUS_CHOICES,
            "selected_school": school_id,
            "selected_course": course_id,
            "selected_year": year_val,
            "selected_type": leave_type,
            "selected_status": status_val,
            "search_q": search_q,
        },
    )


# ============================================================
# 11. SECURE DOCUMENT DOWNLOAD
# ============================================================

@login_required(login_url="/accounts/login/")
def download_document(request, pk):
    """
    Streams the supporting document to authorized users only.
    Prevents unauthorized URL scraping or directory exposure.
    """
    leave = get_object_or_404(StudentLeaveRequest, pk=pk)

    if not leave.supporting_document:
        raise Http404("No supporting document uploaded for this leave request.")

    ctx_role = get_current_user_profile(request.user)
    is_owner = ctx_role["student"] and (leave.student == ctx_role["student"])
    is_authorized_faculty = ctx_role["faculty"] and is_faculty_authorized_for_student(ctx_role["faculty"], leave.student)
    is_authorized_incharge = ctx_role["is_incharge"] and (ctx_role["is_incharge"].department_id == leave.student.department_id)
    is_admin = ctx_role["is_admin"]

    if not (is_owner or is_authorized_faculty or is_authorized_incharge or is_admin):
        return HttpResponseForbidden("You do not have permission to download this document.")

    file_path = leave.supporting_document.path
    if not os.path.exists(file_path):
        raise Http404("Document file could not be found on server.")

    response = FileResponse(open(file_path, "rb"))
    filename = os.path.basename(file_path)
    response["Content-Disposition"] = f'inline; filename="{filename}"'
    return response
