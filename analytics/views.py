import json
from decimal import Decimal
from urllib.parse import urlencode

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.http import HttpResponse, HttpResponseForbidden
from django.utils import timezone

from students.models import Student
from faculty.models import Faculty
from . import services, reports


def _build_query_string(params, exclude_keys=None):
    if exclude_keys is None:
        exclude_keys = []
    clean = {}
    for k, v in params.items():
        if k not in exclude_keys and v:
            clean[k] = v
    return urlencode(clean)


# ==============================================================================
# 1. MAIN ANALYTICS DASHBOARD (/analytics/)
# ==============================================================================

@login_required(login_url="/accounts/login/")
def dashboard_view(request):
    scope = services.get_analytics_scope(request.user, request.GET)
    if not scope:
        return redirect("/accounts/login/")

    # If student, redirect directly to personal analytics
    if scope["role"] == "student":
        return redirect("/analytics/my/")

    kpi = services.get_kpi_summary(scope)
    academic = services.get_academic_analytics(scope)
    attendance = services.get_attendance_analytics(scope)
    risk = services.get_risk_student_analytics(scope)
    insights = services.get_ai_insights(scope, kpi, academic, attendance, risk)

    # Charts JSON data
    # 1. Subject Marks chart
    subj_names = [s["name"] for s in academic["subjects"][:7]]
    subj_scores = [s["avg_percentage"] for s in academic["subjects"][:7]]

    # 2. Attendance distribution chart
    att_dist_labels = ["Safe (>=75%)", "Warning (65-74.9%)", "Critical (<65%)"]
    att_dist_values = [attendance["safe_count"], attendance["warning_count"], attendance["critical_count"]]

    # 3. Marks distribution chart
    marks_dist_labels = ["Distinction (>=75%)", "First Class (60-74%)", "Second Class (50-59%)", "Pass (40-49%)", "Fail (<40%)"]
    marks_dist_values = [
        academic["distribution"]["distinction"],
        academic["distribution"]["first_class"],
        academic["distribution"]["second_class"],
        academic["distribution"]["pass_class"],
        academic["distribution"]["fail_class"],
    ]

    # 4. Fee collection chart
    fees = services.get_fees_analytics(scope)
    fee_chart_labels = ["Collected Fees", "Outstanding Balance"]
    fee_chart_values = [float(kpi["fees_collected"]), float(kpi["fees_outstanding"])]

    charts_json = json.dumps({
        "subjects": {"labels": subj_names, "data": subj_scores},
        "attendance": {"labels": att_dist_labels, "data": att_dist_values},
        "marks_dist": {"labels": marks_dist_labels, "data": marks_dist_values},
        "fees": {"labels": fee_chart_labels, "data": fee_chart_values},
    })

    export_params = _build_query_string(request.GET)
    reset_url = "/analytics/"

    return render(request, "analytics/dashboard.html", {
        "scope": scope,
        "kpi": kpi,
        "academic": academic,
        "attendance": attendance,
        "risk": risk,
        "insights": insights,
        "fees": fees,
        "charts_json": charts_json,
        "export_params": export_params,
        "reset_url": reset_url,
        "current_tab": "overview",
    })


# ==============================================================================
# 2. ACADEMIC PERFORMANCE ANALYTICS (/analytics/academic/)
# ==============================================================================

@login_required(login_url="/accounts/login/")
def academic_analytics_view(request):
    scope = services.get_analytics_scope(request.user, request.GET)
    if not scope:
        return redirect("/accounts/login/")
    if scope["role"] == "student":
        return redirect("/analytics/my/")

    kpi = services.get_kpi_summary(scope)
    academic = services.get_academic_analytics(scope)

    # Charts JSON
    subj_names = [s["name"] for s in academic["subjects"]]
    subj_scores = [s["avg_percentage"] for s in academic["subjects"]]
    subj_pass = [s["pass_rate"] for s in academic["subjects"]]

    crs_names = [c["name"] for c in academic["courses"] if c["avg_percentage"] is not None]
    crs_scores = [c["avg_percentage"] for c in academic["courses"] if c["avg_percentage"] is not None]

    yr_names = [y["year_label"] for y in academic["years"] if y["avg_percentage"] is not None]
    yr_scores = [y["avg_percentage"] for y in academic["years"] if y["avg_percentage"] is not None]

    charts_json = json.dumps({
        "subjects": {"labels": subj_names, "scores": subj_scores, "pass_rates": subj_pass},
        "courses": {"labels": crs_names, "scores": crs_scores},
        "years": {"labels": yr_names, "scores": yr_scores},
    })

    export_params = _build_query_string(request.GET)

    return render(request, "analytics/academic.html", {
        "scope": scope,
        "kpi": kpi,
        "academic": academic,
        "charts_json": charts_json,
        "export_params": export_params,
        "reset_url": "/analytics/academic/",
        "current_tab": "academic",
    })


# ==============================================================================
# 3. ATTENDANCE ANALYTICS (/analytics/attendance/)
# ==============================================================================

@login_required(login_url="/accounts/login/")
def attendance_analytics_view(request):
    scope = services.get_analytics_scope(request.user, request.GET)
    if not scope:
        return redirect("/accounts/login/")
    if scope["role"] == "student":
        return redirect("/analytics/my/")

    attendance = services.get_attendance_analytics(scope)

    # Pagination for attendance risk list
    paginator = Paginator(attendance["risk_list"], 15)
    page_number = request.GET.get("page", 1)
    page_obj = paginator.get_page(page_number)

    # Charts JSON
    charts_json = json.dumps({
        "distribution": {
            "labels": ["Safe (>= 75%)", "Warning (65% - 74.9%)", "Critical (< 65%)"],
            "data": [attendance["safe_count"], attendance["warning_count"], attendance["critical_count"]],
        },
        "subjects": {
            "labels": [s["name"] for s in attendance["subject_attendance"][:8]],
            "data": [s["attendance_pct"] for s in attendance["subject_attendance"][:8]],
        },
        "courses": {
            "labels": [c["name"] for c in attendance["course_attendance"] if c["attendance_pct"] is not None],
            "data": [c["attendance_pct"] for c in attendance["course_attendance"] if c["attendance_pct"] is not None],
        }
    })

    export_params = _build_query_string(request.GET, exclude_keys=["page"])

    return render(request, "analytics/attendance.html", {
        "scope": scope,
        "attendance": attendance,
        "page_obj": page_obj,
        "charts_json": charts_json,
        "export_params": export_params,
        "reset_url": "/analytics/attendance/",
        "current_tab": "attendance",
    })


# ==============================================================================
# 4. AT-RISK STUDENT IDENTIFICATION (/analytics/risk/)
# ==============================================================================

@login_required(login_url="/accounts/login/")
def risk_students_view(request):
    scope = services.get_analytics_scope(request.user, request.GET)
    if not scope:
        return redirect("/accounts/login/")
    if scope["role"] == "student":
        return redirect("/analytics/my/")

    risk = services.get_risk_student_analytics(scope)

    paginator = Paginator(risk["students"], 15)
    page_number = request.GET.get("page", 1)
    page_obj = paginator.get_page(page_number)

    export_params = _build_query_string(request.GET, exclude_keys=["page"])

    return render(request, "analytics/risk_students.html", {
        "scope": scope,
        "risk": risk,
        "page_obj": page_obj,
        "export_params": export_params,
        "reset_url": "/analytics/risk/",
        "current_tab": "risk",
    })


# ==============================================================================
# 5. FEES ANALYTICS (/analytics/fees/)
# ==============================================================================

@login_required(login_url="/accounts/login/")
def fees_analytics_view(request):
    scope = services.get_analytics_scope(request.user, request.GET)
    if not scope:
        return redirect("/accounts/login/")
    if scope["role"] == "student":
        return redirect("/analytics/my/")

    fees = services.get_fees_analytics(scope)

    paginator = Paginator(fees["fee_risk_list"], 15)
    page_number = request.GET.get("page", 1)
    page_obj = paginator.get_page(page_number)

    charts_json = json.dumps({
        "collection": {
            "labels": ["Paid Amount", "Outstanding Balance"],
            "data": [float(fees["total_paid"]), float(fees["total_outstanding"])],
        },
        "types": {
            "labels": [t["label"] for t in fees["type_distribution"]],
            "total": [t["total_amount"] for t in fees["type_distribution"]],
            "paid": [t["paid_amount"] for t in fees["type_distribution"]],
        }
    })

    export_params = _build_query_string(request.GET, exclude_keys=["page"])

    return render(request, "analytics/fees.html", {
        "scope": scope,
        "fees": fees,
        "page_obj": page_obj,
        "charts_json": charts_json,
        "export_params": export_params,
        "reset_url": "/analytics/fees/",
        "current_tab": "fees",
    })


# ==============================================================================
# 6. LIBRARY ANALYTICS (/analytics/library/)
# ==============================================================================

@login_required(login_url="/accounts/login/")
def library_analytics_view(request):
    scope = services.get_analytics_scope(request.user, request.GET)
    if not scope:
        return redirect("/accounts/login/")
    if scope["role"] == "student":
        return redirect("/analytics/my/")

    library = services.get_library_analytics(scope)

    charts_json = json.dumps({
        "categories": {
            "labels": [c["label"] for c in library["category_distribution"]],
            "data": [c["count"] for c in library["category_distribution"]],
        },
        "status": {
            "labels": ["Available Copies", "Issued Copies"],
            "data": [library["available_copies"], library["issued_copies"]],
        }
    })

    export_params = _build_query_string(request.GET)

    return render(request, "analytics/library.html", {
        "scope": scope,
        "library": library,
        "charts_json": charts_json,
        "export_params": export_params,
        "reset_url": "/analytics/library/",
        "current_tab": "library",
    })


# ==============================================================================
# 7. PLACEMENT ANALYTICS (/analytics/placements/)
# ==============================================================================

@login_required(login_url="/accounts/login/")
def placement_analytics_view(request):
    scope = services.get_analytics_scope(request.user, request.GET)
    if not scope:
        return redirect("/accounts/login/")
    if scope["role"] == "student":
        return redirect("/analytics/my/")

    placements = services.get_placement_analytics(scope)

    charts_json = json.dumps({
        "funnel": {
            "labels": ["Eligible Students", "Registered", "Applied", "Shortlisted", "Selected"],
            "data": [
                placements["eligible_students"],
                placements["registered_students"],
                placements["students_applied"],
                placements["students_shortlisted"],
                placements["students_selected"],
            ],
        }
    })

    export_params = _build_query_string(request.GET)

    return render(request, "analytics/placements.html", {
        "scope": scope,
        "placements": placements,
        "charts_json": charts_json,
        "export_params": export_params,
        "reset_url": "/analytics/placements/",
        "current_tab": "placements",
    })


# ==============================================================================
# 8. CERTIFICATES & DOCUMENTS ANALYTICS (/analytics/certificates/)
# ==============================================================================

@login_required(login_url="/accounts/login/")
def certificate_analytics_view(request):
    scope = services.get_analytics_scope(request.user, request.GET)
    if not scope:
        return redirect("/accounts/login/")
    if scope["role"] == "student":
        return redirect("/analytics/my/")

    certs = services.get_certificate_analytics(scope)

    charts_json = json.dumps({
        "requests": {
            "labels": ["Pending", "Under Review", "Approved", "Generated", "Rejected"],
            "data": [
                certs["pending_count"],
                certs["under_review_count"],
                certs["approved_count"],
                certs["generated_count"],
                certs["rejected_count"],
            ],
        },
        "docs": {
            "labels": ["Pending Verification", "Verified", "Rejected"],
            "data": [certs["doc_pending"], certs["doc_verified"], certs["doc_rejected"]],
        }
    })

    export_params = _build_query_string(request.GET)

    return render(request, "analytics/certificates.html", {
        "scope": scope,
        "certificates": certs,
        "charts_json": charts_json,
        "export_params": export_params,
        "reset_url": "/analytics/certificates/",
        "current_tab": "certificates",
    })


# ==============================================================================
# 9. FACULTY WORKLOAD & ANALYTICS (/analytics/faculty/)
# ==============================================================================

@login_required(login_url="/accounts/login/")
def faculty_analytics_view(request):
    scope = services.get_analytics_scope(request.user, request.GET)
    if not scope:
        return redirect("/accounts/login/")
    if scope["role"] == "student":
        return redirect("/analytics/my/")

    faculty_data = services.get_faculty_analytics(scope)

    paginator = Paginator(faculty_data["workload_table"], 15)
    page_number = request.GET.get("page", 1)
    page_obj = paginator.get_page(page_number)

    export_params = _build_query_string(request.GET, exclude_keys=["page"])

    return render(request, "analytics/faculty.html", {
        "scope": scope,
        "faculty_data": faculty_data,
        "page_obj": page_obj,
        "export_params": export_params,
        "reset_url": "/analytics/faculty/",
        "current_tab": "faculty",
    })


# ==============================================================================
# 10. STUDENT PERSONAL ANALYTICS (/analytics/my/)
# ==============================================================================

@login_required(login_url="/accounts/login/")
def student_analytics_view(request, student_id=None):
    """
    Renders personal student analytics.
    Enforces strict access control:
    - Logged-in students can ONLY see their own data.
    - Staff / Admin can inspect an enrolled student via ?student_id= or parameter.
    - Any student attempting to inspect another student receives 403 Forbidden.
    """
    user = request.user
    is_admin = user.is_superuser or user.is_staff

    if is_admin:
        req_id = student_id or request.GET.get("student_id")
        if req_id:
            target_student = get_object_or_404(Student, id=req_id)
        else:
            # Pick first active student or student linked to admin
            target_student = Student.objects.filter(user=user).first() or Student.objects.first()
            if not target_student:
                return render(request, "analytics/my_analytics.html", {"error": "No students found."})
    else:
        # Non-admin user: must be a registered student
        target_student = Student.objects.filter(user=user).first()
        if not target_student:
            return redirect("/accounts/login/")

        # If a non-admin student attempted URL manipulation to inspect someone else:
        if student_id and str(student_id) != str(target_student.id):
            return HttpResponseForbidden("Access Denied: You cannot view another student's private analytics.")
        if request.GET.get("student_id") and str(request.GET.get("student_id")) != str(target_student.id):
            return HttpResponseForbidden("Access Denied: You cannot view another student's private analytics.")

    analytics_data = services.get_student_personal_analytics(target_student)

    # Subject attendance chart for personal dashboard
    subj_att = analytics_data["attendance"]["subjects"]
    charts_json = json.dumps({
        "subjects": {
            "labels": [s["subject"] for s in subj_att],
            "percentages": [s["percentage"] for s in subj_att],
        }
    })

    return render(request, "analytics/my_analytics.html", {
        "data": analytics_data,
        "student": target_student,
        "charts_json": charts_json,
        "is_admin_view": is_admin,
        "generated_at": timezone.now(),
        "current_tab": "my",
    })


# ==============================================================================
# 11. EXPORT TO EXCEL (/analytics/export/excel/)
# ==============================================================================

@login_required(login_url="/accounts/login/")
def export_excel_view(request):
    scope = services.get_analytics_scope(request.user, request.GET)
    if not scope:
        return redirect("/accounts/login/")
    if scope["role"] == "student":
        return HttpResponseForbidden("Export restricted to staff and authorized personnel.")

    export_type = request.GET.get("type", "overall").lower()
    if export_type not in ["overall", "risk", "attendance", "academic", "fees", "faculty"]:
        export_type = "overall"

    return reports.generate_analytics_excel(scope, export_type=export_type)


# ==============================================================================
# 12. EXPORT TO PDF (/analytics/export/pdf/)
# ==============================================================================

@login_required(login_url="/accounts/login/")
def export_pdf_view(request):
    scope = services.get_analytics_scope(request.user, request.GET)
    if not scope:
        return redirect("/accounts/login/")
    if scope["role"] == "student":
        return HttpResponseForbidden("Export restricted to staff and authorized personnel.")

    export_type = request.GET.get("type", "overall").lower()
    if export_type not in ["overall", "risk", "attendance", "academic", "fees", "faculty"]:
        export_type = "overall"

    return reports.generate_analytics_pdf(scope, export_type=export_type)
