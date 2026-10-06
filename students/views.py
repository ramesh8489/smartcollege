from timetable.models import Circular
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required

from .models import Student
from attendance.models import Attendance
from marks.models import Marks


# ============================================================
# STUDENT ACCESS CHECK
# ============================================================

def get_student_or_redirect(request):

    student = Student.objects.filter(
        user=request.user
    ).first()

    if student:
        return student, None

    from faculty.models import Faculty

    # Faculty user
    if Faculty.objects.filter(
        email=request.user.email
    ).exists():

        return None, redirect("/faculty/")

    # Admin user
    if request.user.is_superuser:

        return None, redirect(
            "/accounts/admin-dashboard/"
        )

    # Unknown user
    return None, redirect(
        "/accounts/login/"
    )


# ============================================================
# STUDENT DASHBOARD
# ============================================================

@login_required(login_url="/accounts/login/")
def dashboard(request):

    student, redirect_response = get_student_or_redirect(
        request
    )

    if redirect_response:
        return redirect_response

    students = Student.objects.filter(
        user=request.user
    )

    attendance_records = Attendance.objects.filter(
        student=student
    )

    total_classes = attendance_records.count()

    present_classes = attendance_records.filter(
        present=True
    ).count()

    if total_classes > 0:

        attendance_percentage = round(
            (present_classes / total_classes) * 100,
            2
        )

    else:

        attendance_percentage = 0


    # ========================================================
    # SUBJECT-WISE ATTENDANCE
    # ========================================================

    subjects = attendance_records.values(
        "subject"
    ).distinct()

    subject_attendance = []

    for item in subjects:

        subject_id = item["subject"]

        records = attendance_records.filter(
            subject_id=subject_id
        )

        total = records.count()

        present = records.filter(
            present=True
        ).count()

        if total > 0:

            percentage = round(
                (present / total) * 100,
                2
            )

        else:

            percentage = 0

        subject = records.first().subject

        subject_attendance.append({

            "subject": subject,

            "total": total,

            "present": present,

            "percentage": percentage,

        })


    # ========================================================
    # MARKS
    # ========================================================

    marks = Marks.objects.filter(
        student=student
    ).select_related(
        "subject"
    )

    marks_summary = []

    for mark in marks:

        total = mark.grand_total

        average = round(
            total / 3,
            2
        )

        percentage = round(
            (total / 150) * 100,
            2
        )


        # ====================================================
        # GRADE
        # ====================================================

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


        marks_summary.append({

            "mark": mark,

            "total": total,

            "average": average,

            "percentage": percentage,

            "grade": grade,

        })


    # ========================================================
    # EXAM RESULTS (NEW)
    # ========================================================

    from exams.models import StudentExamMark, compute_grade_and_points

    student_exam_marks = StudentExamMark.objects.filter(
        student=student
    ).select_related("exam", "subject").order_by("-exam__start_date", "subject__name")

    exam_results_grouped = {}
    for em in student_exam_marks:
        if em.exam_id not in exam_results_grouped:
            exam_results_grouped[em.exam_id] = {
                "exam": em.exam,
                "marks": [],
            }
        exam_results_grouped[em.exam_id]["marks"].append(em)

    student_exam_reports = []
    for grp in exam_results_grouped.values():
        exam_obj = grp["exam"]
        m_list = grp["marks"]
        tot_obt = sum(m.marks_obtained for m in m_list)
        tot_max = sum(m.max_marks for m in m_list)
        ovr_pct = round((float(tot_obt) / float(tot_max)) * 100, 2) if tot_max > 0 else 0.0
        ovr_res = "Pass" if all(m.result_status == "Pass" for m in m_list) else "Fail"
        ovr_grd, _, _ = compute_grade_and_points(ovr_pct)

        student_exam_reports.append({
            "exam": exam_obj,
            "marks": m_list,
            "total_obtained": tot_obt,
            "total_max": tot_max,
            "overall_percentage": ovr_pct,
            "overall_result": ovr_res,
            "overall_grade": ovr_grd,
        })

    # ========================================================
    # ASSIGNMENTS (STUDENT DASHBOARD)
    # ========================================================
    from assignments.models import Assignment, AssignmentSubmission

    student_assignments = Assignment.objects.filter(
        course=student.course,
        year=student.year,
        is_active=True
    ).select_related("subject", "faculty").order_by("submission_deadline")

    student_submissions_map = {
        s.assignment_id: s
        for s in AssignmentSubmission.objects.filter(student=student, assignment__in=student_assignments)
    }

    assignment_dashboard_items = []
    for a in student_assignments:
        sub = student_submissions_map.get(a.id)
        status_val = sub.status if sub else ("Late" if a.is_deadline_passed else "Not Submitted")
        assignment_dashboard_items.append({
            "assignment": a,
            "submission": sub,
            "status": status_val,
            "marks": sub.marks_obtained if sub and sub.marks_obtained is not None else None,
            "feedback": sub.feedback if sub and sub.feedback else "",
        })

    # ========================================================
    # LEAVE MANAGEMENT (STUDENT DASHBOARD)
    # ========================================================
    from student_leave.models import StudentLeaveRequest

    all_student_leaves = StudentLeaveRequest.objects.filter(student=student)
    leave_total_requests = all_student_leaves.count()
    leave_pending_requests = all_student_leaves.filter(
        status__in=[
            StudentLeaveRequest.STATUS_PENDING,
            StudentLeaveRequest.STATUS_FACULTY_APPROVED,
            StudentLeaveRequest.STATUS_INCHARGE_APPROVED,
        ]
    ).count()
    leave_approved_requests = all_student_leaves.filter(
        status=StudentLeaveRequest.STATUS_ADMIN_APPROVED
    ).count()
    leave_rejected_requests = all_student_leaves.filter(
        status__in=[
            StudentLeaveRequest.STATUS_FACULTY_REJECTED,
            StudentLeaveRequest.STATUS_INCHARGE_REJECTED,
            StudentLeaveRequest.STATUS_ADMIN_REJECTED,
        ]
    ).count()
    recent_student_leaves = all_student_leaves.order_by("-applied_date")[:5]

    # ========================================================
    # TRAINING & PLACEMENTS (STUDENT DASHBOARD)
    # ========================================================
    from placements.models import PlacementDrive, PlacementApplication, PlacementResult

    placement_open_drives = PlacementDrive.objects.filter(status=PlacementDrive.STATUS_OPEN).select_related("company").order_by("application_deadline")
    placement_open_drives_count = placement_open_drives.count()
    placement_my_apps = PlacementApplication.objects.filter(student=student)
    placement_my_applications_count = placement_my_apps.count()
    placement_shortlisted_count = placement_my_apps.filter(
        status__in=[PlacementApplication.STATUS_SHORTLISTED, PlacementApplication.STATUS_INTERVIEW]
    ).count()
    placement_offers_count = PlacementResult.objects.filter(student=student, result="Selected").count()
    placement_recent_drives = placement_open_drives[:4]

    # ========================================================
    # CERTIFICATES & DOCUMENTS (STUDENT DASHBOARD)
    # ========================================================
    from certificates.models import CertificateRequest, StudentDocument
    student_cert_requests = CertificateRequest.objects.filter(student=student)
    cert_requests_count = student_cert_requests.count()
    cert_pending_count = student_cert_requests.filter(
        status__in=[CertificateRequest.STATUS_PENDING, CertificateRequest.STATUS_UNDER_REVIEW]
    ).count()
    cert_approved_count = student_cert_requests.filter(
        status__in=[CertificateRequest.STATUS_APPROVED, CertificateRequest.STATUS_GENERATED, CertificateRequest.STATUS_DOWNLOADED]
    ).count()
    student_docs = StudentDocument.objects.filter(student=student)
    docs_total_count = student_docs.count()
    docs_pending_count = student_docs.filter(verification_status=StudentDocument.STATUS_PENDING).count()

    # ========================================================
    # HOSTEL PORTAL INTEGRATION (PHASE 10)
    # ========================================================
    from hostel.services import get_student_hostel_summary
    hostel_summary = get_student_hostel_summary(student)

    # ========================================================
    # FEES & ONLINE PAYMENTS INTEGRATION
    # ========================================================
    from decimal import Decimal
    from fees.models import FeeRecord, FeePayment

    student_fee_records = list(
        FeeRecord.objects.filter(student=student)
        .prefetch_related("payments")
        .order_by("-created_at")
    )
    fee_total_amount = sum((r.amount for r in student_fee_records), Decimal("0.00"))
    fee_total_paid = sum((r.paid_amount for r in student_fee_records), Decimal("0.00"))
    fee_total_balance = max(fee_total_amount - fee_total_paid, Decimal("0.00"))

    student_recent_payments = list(
        FeePayment.objects.filter(fee_record__student=student)
        .select_related("fee_record")
        .order_by("-payment_date", "-created_at")[:5]
    )

    fee_summary = {
        "records": student_fee_records,
        "total_amount": fee_total_amount,
        "total_paid": fee_total_paid,
        "total_balance": fee_total_balance,
        "pending_records": [r for r in student_fee_records if r.balance_amount > 0],
        "paid_records": [r for r in student_fee_records if r.balance_amount == 0],
        "recent_payments": student_recent_payments,
        "record_count": len(student_fee_records),
        "has_pending": fee_total_balance > 0,
    }

    # ========================================================
    # DASHBOARD
    # ========================================================

    return render(
        request,
        "students/dashboard.html",
        {
            "student": student,

            "students": students,

            "attendance_percentage":
                attendance_percentage,

            "total_classes":
                total_classes,

            "present_classes":
                present_classes,

            "subject_attendance":
                subject_attendance,

            "marks":
                marks,

            "marks_summary":
                marks_summary,

            "student_exam_reports":
                student_exam_reports,

            "student_assignments_list":
                assignment_dashboard_items,

            "leave_total_requests":
                leave_total_requests,

            "leave_pending_requests":
                leave_pending_requests,

            "leave_approved_requests":
                leave_approved_requests,

            "leave_rejected_requests":
                leave_rejected_requests,

            "recent_student_leaves":
                recent_student_leaves,

            "placement_open_drives_count":
                placement_open_drives_count,

            "placement_my_applications_count":
                placement_my_applications_count,

            "placement_shortlisted_count":
                placement_shortlisted_count,

            "placement_offers_count":
                placement_offers_count,

            "placement_recent_drives":
                placement_recent_drives,

            "cert_requests_count":
                cert_requests_count,

            "cert_pending_count":
                cert_pending_count,

            "cert_approved_count":
                cert_approved_count,

            "docs_total_count":
                docs_total_count,

            "docs_pending_count":
                docs_pending_count,

            "hostel_summary":
                hostel_summary,

            "fee_summary":
                fee_summary,

            "recent_circulars":
                Circular.objects.filter(
                    audience__in=["ALL", "STUDENT"]
                )[:3],
        }
    )


# ============================================================
# ATTENDANCE HISTORY
# ============================================================

@login_required(login_url="/accounts/login/")
def attendance_history(request):

    student, redirect_response = get_student_or_redirect(
        request
    )

    if redirect_response:
        return redirect_response

    attendance_records = Attendance.objects.filter(
        student=student
    ).select_related(
        "subject"
    ).order_by(
        "-date"
    )


    # ========================================================
    # SUBJECT FILTER
    # ========================================================

    subject_id = request.GET.get(
        "subject"
    )

    if subject_id:

        attendance_records = attendance_records.filter(
            subject_id=subject_id
        )


    # ========================================================
    # DATE FILTER
    # ========================================================

    date = request.GET.get(
        "date"
    )

    if date:

        attendance_records = attendance_records.filter(
            date=date
        )


    # ========================================================
    # STATISTICS
    # ========================================================

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


    # ========================================================
    # SUBJECT LIST
    # ========================================================

    subjects = Attendance.objects.filter(
        student=student
    ).select_related(
        "subject"
    ).values(
        "subject",
        "subject__name",
        "subject__code"
    ).distinct()


    return render(
        request,
        "students/attendance_history.html",
        {
            "student":
                student,

            "attendance_records":
                attendance_records,

            "subjects":
                subjects,

            "selected_subject":
                subject_id,

            "selected_date":
                date,

            "total_classes":
                total_classes,

            "present_classes":
                present_classes,

            "absent_classes":
                absent_classes,

            "attendance_percentage":
                attendance_percentage,
        }
    )


# ============================================================
# MARKS HISTORY
# ============================================================

@login_required(login_url="/accounts/login/")
def marks_history(request):

    student, redirect_response = get_student_or_redirect(
        request
    )

    if redirect_response:
        return redirect_response

    marks_records = Marks.objects.filter(
        student=student
    ).select_related(
        "subject"
    ).order_by(
        "subject__name"
    )


    # ========================================================
    # SUBJECT FILTER
    # ========================================================

    subject_id = request.GET.get(
        "subject"
    )

    if subject_id:

        marks_records = marks_records.filter(
            subject_id=subject_id
        )


    # ========================================================
    # MARKS SUMMARY
    # ========================================================

    marks_summary = []

    for mark in marks_records:

        total = mark.grand_total

        average = round(
            total / 3,
            2
        )

        percentage = round(
            (total / 150) * 100,
            2
        )


        # ====================================================
        # GRADE
        # ====================================================

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


        marks_summary.append({

            "mark":
                mark,

            "total":
                total,

            "average":
                average,

            "percentage":
                percentage,

            "grade":
                grade,

        })


    # ========================================================
    # OVERALL MARKS
    # ========================================================

    total_subjects = len(
        marks_summary
    )

    total_marks = sum(
        item["total"]
        for item in marks_summary
    )

    maximum_marks = (
        total_subjects * 120
    )


    if maximum_marks > 0:

        overall_percentage = round(
            (
                total_marks
                / maximum_marks
            ) * 100,
            2
        )

    else:

        overall_percentage = 0


    # ========================================================
    # SUBJECT LIST
    # ========================================================

    subjects = Marks.objects.filter(
        student=student
    ).select_related(
        "subject"
    ).values(
        "subject",
        "subject__name",
        "subject__code"
    ).distinct()


    return render(
        request,
        "students/marks_history.html",
        {
            "student":
                student,

            "marks_summary":
                marks_summary,

            "subjects":
                subjects,

            "selected_subject":
                subject_id,

            "total_subjects":
                total_subjects,

            "total_marks":
                total_marks,

            "overall_percentage":
                overall_percentage,
        }
    )


# ============================================================
# STUDENT PROFILE
# ============================================================

@login_required(login_url="/accounts/login/")
def profile(request):

    student, redirect_response = get_student_or_redirect(
        request
    )

    if redirect_response:
        return redirect_response


    return render(
        request,
        "students/profile.html",
        {
            "student":
                student,
        }
    )
