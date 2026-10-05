import os
from decimal import Decimal
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponseForbidden, FileResponse, Http404
from django.utils import timezone
from django.db.models import Q, Count, Avg
from django.contrib.auth.models import User

from .models import (
    Company,
    PlacementDrive,
    PlacementApplication,
    PlacementRound,
    PlacementResult,
    StudentPlacementProfile,
)
from .forms import (
    CompanyForm,
    PlacementDriveForm,
    PlacementApplicationForm,
    PlacementRoundForm,
    PlacementResultForm,
    StudentPlacementProfileForm,
)
from .services import check_student_eligibility, get_student_academic_summary
from students.models import Student, Department, Course
from faculty.models import Faculty
from timetable.models import Notification


def notify_user(user, title, message, link=""):
    """Reuses the existing SmartCollege Notification system."""
    if user and user.is_authenticated:
        try:
            Notification.objects.create(
                recipient=user,
                title=title,
                message=message,
                link=link or "/placements/",
            )
        except Exception:
            pass


def get_user_role(user):
    """Identifies role of authenticated user."""
    student = Student.objects.filter(user=user).select_related("course", "department").first()
    faculty = Faculty.objects.filter(user=user).first() or Faculty.objects.filter(email=user.email).first()
    is_admin = bool(user and (user.is_superuser or user.is_staff))

    if is_admin:
        role = "admin"
    elif student:
        role = "student"
    elif faculty:
        role = "faculty"
    else:
        role = "guest"

    return {
        "role": role,
        "student": student,
        "faculty": faculty,
        "is_officer": is_admin,
        "is_admin": is_admin,
    }


# ============================================================
# 1. PLACEMENT OFFICER / ADMIN DASHBOARD
# ============================================================

@login_required(login_url="/accounts/login/")
def dashboard(request):
    """
    Placement Officer / Admin central dashboard.
    Dispatches students directly to their student placement portal.
    """
    ctx_role = get_user_role(request.user)
    if ctx_role["role"] == "student":
        return redirect("student_placement_portal")

    today = timezone.localdate()

    # Metrics
    total_companies = Company.objects.count()
    active_companies = Company.objects.filter(status=Company.STATUS_ACTIVE).count()
    total_drives = PlacementDrive.objects.count()
    upcoming_drives = PlacementDrive.objects.filter(drive_date__gte=today).count()

    total_applications = PlacementApplication.objects.count()
    shortlisted_applications = PlacementApplication.objects.filter(
        status__in=[PlacementApplication.STATUS_SHORTLISTED, PlacementApplication.STATUS_INTERVIEW]
    ).count()
    selected_applications = PlacementApplication.objects.filter(status=PlacementApplication.STATUS_SELECTED).count()

    placed_students_count = PlacementResult.objects.filter(result="Selected").values("student").distinct().count()
    total_students_pool = Student.objects.filter(is_active=True).count()
    placement_percentage = (
        round((Decimal(placed_students_count) / Decimal(total_students_pool)) * 100, 1)
        if total_students_pool > 0
        else Decimal("0.0")
    )

    # Activity & Tables
    recent_drives = PlacementDrive.objects.select_related("company").order_by("-created_at")[:6]
    recent_applications = PlacementApplication.objects.select_related(
        "student__course", "placement_drive__company"
    ).order_by("-application_date")[:8]
    recent_results = PlacementResult.objects.select_related("student", "company").order_by("-result_date")[:6]

    # Course-wise & Department-wise Placement Statistics
    dept_stats = (
        PlacementResult.objects.filter(result="Selected")
        .values("student__department__name")
        .annotate(total_placed=Count("student", distinct=True))
        .order_by("-total_placed")
    )

    course_stats = (
        PlacementResult.objects.filter(result="Selected")
        .values("student__course__name")
        .annotate(total_placed=Count("student", distinct=True))
        .order_by("-total_placed")[:5]
    )

    return render(
        request,
        "placements/dashboard.html",
        {
            "total_companies": total_companies,
            "active_companies": active_companies,
            "total_drives": total_drives,
            "upcoming_drives": upcoming_drives,
            "total_applications": total_applications,
            "shortlisted_applications": shortlisted_applications,
            "selected_applications": selected_applications,
            "placed_students_count": placed_students_count,
            "placement_percentage": placement_percentage,
            "recent_drives": recent_drives,
            "recent_applications": recent_applications,
            "recent_results": recent_results,
            "dept_stats": dept_stats,
            "course_stats": course_stats,
        },
    )


# ============================================================
# 2. COMPANY MANAGEMENT
# ============================================================

@login_required(login_url="/accounts/login/")
def company_list(request):
    """Lists all partner recruiting companies with search and filtering."""
    ctx_role = get_user_role(request.user)
    is_officer = ctx_role["is_officer"]

    qs = Company.objects.all().order_by("name")

    search_q = request.GET.get("q", "").strip()
    status_filter = request.GET.get("status", "").strip()
    industry_filter = request.GET.get("industry", "").strip()

    if search_q:
        qs = qs.filter(Q(name__icontains=search_q) | Q(industry__icontains=search_q))
    if status_filter:
        qs = qs.filter(status=status_filter)
    if industry_filter:
        qs = qs.filter(industry__icontains=industry_filter)

    industries = Company.objects.values_list("industry", flat=True).distinct()

    return render(
        request,
        "placements/company_list.html",
        {
            "companies": qs,
            "search_q": search_q,
            "status_filter": status_filter,
            "industry_filter": industry_filter,
            "industries": sorted(set(filter(None, industries))),
            "is_officer": is_officer,
        },
    )


@login_required(login_url="/accounts/login/")
def company_create(request):
    """Add a new recruiting company."""
    ctx_role = get_user_role(request.user)
    if not ctx_role["is_officer"]:
        return HttpResponseForbidden("Placement officer privileges required.")

    if request.method == "POST":
        form = CompanyForm(request.POST, request.FILES)
        if form.is_valid():
            company = form.save()
            messages.success(request, f"Company '{company.name}' registered successfully.")
            return redirect("company_detail", pk=company.pk)
    else:
        form = CompanyForm()

    return render(request, "placements/company_form.html", {"form": form, "action_title": "Register Company"})


@login_required(login_url="/accounts/login/")
def company_edit(request, pk):
    """Edit existing recruiting company."""
    ctx_role = get_user_role(request.user)
    if not ctx_role["is_officer"]:
        return HttpResponseForbidden("Placement officer privileges required.")

    company = get_object_or_404(Company, pk=pk)
    if request.method == "POST":
        form = CompanyForm(request.POST, request.FILES, instance=company)
        if form.is_valid():
            form.save()
            messages.success(request, f"Company '{company.name}' updated successfully.")
            return redirect("company_detail", pk=company.pk)
    else:
        form = CompanyForm(instance=company)

    return render(
        request,
        "placements/company_form.html",
        {"form": form, "company": company, "action_title": f"Edit {company.name}"},
    )


@login_required(login_url="/accounts/login/")
def company_detail(request, pk):
    """Detail page of a company with drives and recruitment records."""
    company = get_object_or_404(Company, pk=pk)
    ctx_role = get_user_role(request.user)

    drives = company.drives.all().order_by("-drive_date")
    results = company.placement_results.filter(result="Selected").select_related("student__course")

    return render(
        request,
        "placements/company_detail.html",
        {
            "company": company,
            "drives": drives,
            "results": results,
            "is_officer": ctx_role["is_officer"],
        },
    )


@login_required(login_url="/accounts/login/")
def company_delete(request, pk):
    """Deactivate or remove company."""
    ctx_role = get_user_role(request.user)
    if not ctx_role["is_officer"]:
        return HttpResponseForbidden("Placement officer privileges required.")

    company = get_object_or_404(Company, pk=pk)
    if request.method == "POST":
        company_name = company.name
        # Soft-deactivate if drives exist, or delete
        if company.drives.exists():
            company.status = Company.STATUS_INACTIVE
            company.save()
            messages.warning(request, f"Company '{company_name}' deactivated (has active placement drives).")
        else:
            company.delete()
            messages.success(request, f"Company '{company_name}' deleted.")
        return redirect("company_list")

    return render(request, "placements/company_confirm_delete.html", {"company": company})


# ============================================================
# 3. PLACEMENT DRIVES
# ============================================================

@login_required(login_url="/accounts/login/")
def drive_list(request):
    """List placement drives with comprehensive filters."""
    ctx_role = get_user_role(request.user)
    is_officer = ctx_role["is_officer"]

    qs = PlacementDrive.objects.select_related("company").order_by("-drive_date")

    # Filters
    company_id = request.GET.get("company", "").strip()
    status_filter = request.GET.get("status", "").strip()
    emp_type = request.GET.get("emp_type", "").strip()
    search_q = request.GET.get("q", "").strip()

    if company_id:
        qs = qs.filter(company_id=company_id)
    if status_filter:
        qs = qs.filter(status=status_filter)
    if emp_type:
        qs = qs.filter(employment_type=emp_type)
    if search_q:
        qs = qs.filter(
            Q(job_title__icontains=search_q)
            | Q(company__name__icontains=search_q)
            | Q(job_location__icontains=search_q)
        )

    companies = Company.objects.all().order_by("name")

    return render(
        request,
        "placements/drive_list.html",
        {
            "drives": qs,
            "companies": companies,
            "status_filter": status_filter,
            "emp_type": emp_type,
            "selected_company": company_id,
            "search_q": search_q,
            "is_officer": is_officer,
            "status_choices": PlacementDrive.STATUS_CHOICES,
            "emp_choices": PlacementDrive.EMPLOYMENT_CHOICES,
        },
    )


@login_required(login_url="/accounts/login/")
def drive_create(request):
    """Create a new placement drive."""
    ctx_role = get_user_role(request.user)
    if not ctx_role["is_officer"]:
        return HttpResponseForbidden("Placement officer privileges required.")

    if request.method == "POST":
        form = PlacementDriveForm(request.POST)
        if form.is_valid():
            drive = form.save()

            # If published as Open, notify eligible graduating students!
            if drive.status == PlacementDrive.STATUS_OPEN:
                target_students = Student.objects.filter(is_active=True)
                if drive.eligible_year != 0:
                    target_students = target_students.filter(year=drive.eligible_year)
                for s in target_students:
                    if s.user:
                        notify_user(
                            s.user,
                            title="New Placement Drive Available",
                            message=f"{drive.company.name} is hiring for '{drive.job_title}' with package {drive.salary_package}. Check your eligibility and apply!",
                            link=f"/placements/drives/{drive.pk}/",
                        )

            messages.success(request, f"Placement drive for '{drive.job_title}' created successfully.")
            return redirect("drive_detail", pk=drive.pk)
    else:
        form = PlacementDriveForm()

    return render(request, "placements/drive_form.html", {"form": form, "action_title": "Schedule Placement Drive"})


@login_required(login_url="/accounts/login/")
def drive_edit(request, pk):
    """Edit placement drive."""
    ctx_role = get_user_role(request.user)
    if not ctx_role["is_officer"]:
        return HttpResponseForbidden("Placement officer privileges required.")

    drive = get_object_or_404(PlacementDrive, pk=pk)
    if request.method == "POST":
        form = PlacementDriveForm(request.POST, instance=drive)
        if form.is_valid():
            form.save()
            messages.success(request, f"Placement drive '{drive.job_title}' updated.")
            return redirect("drive_detail", pk=drive.pk)
    else:
        form = PlacementDriveForm(instance=drive)

    return render(request, "placements/drive_form.html", {"form": form, "drive": drive, "action_title": f"Edit {drive.job_title}"})


@login_required(login_url="/accounts/login/")
def drive_detail(request, pk):
    """Detailed view of a placement drive for officers and students."""
    drive = get_object_or_404(PlacementDrive.objects.select_related("company"), pk=pk)
    ctx_role = get_user_role(request.user)

    applications = drive.applications.select_related("student__course", "student__department").order_by("-application_date")
    results = drive.placement_results.all()

    # If user is student, evaluate their personal eligibility
    student_eligibility = None
    student_application = None
    if ctx_role["role"] == "student" and ctx_role["student"]:
        student = ctx_role["student"]
        is_eligible, reasons = check_student_eligibility(student, drive)
        student_eligibility = {"is_eligible": is_eligible, "reasons": reasons}
        student_application = applications.filter(student=student).first()

    return render(
        request,
        "placements/drive_detail.html",
        {
            "drive": drive,
            "applications": applications,
            "results": results,
            "is_officer": ctx_role["is_officer"],
            "student_eligibility": student_eligibility,
            "student_application": student_application,
        },
    )


# ============================================================
# 4. STUDENT PLACEMENT PORTAL & APPLICATION FLOW
# ============================================================

@login_required(login_url="/accounts/login/")
def student_portal(request):
    """
    Dedicated Student Placement Dashboard:
    - Available placement drives with live eligibility indicator
    - Active applications & status tracker
    - Upcoming interview schedules
    - Final placement offers & CTC
    """
    ctx_role = get_user_role(request.user)
    student = ctx_role["student"]
    if not student:
        messages.error(request, "Only enrolled students can access the student placement portal.")
        return redirect("placements_dashboard")

    today = timezone.localdate()

    # All open drives
    open_drives = PlacementDrive.objects.filter(status=PlacementDrive.STATUS_OPEN).select_related("company").order_by("application_deadline")

    # Evaluate eligibility for every open drive
    drives_with_eligibility = []
    eligible_drives_count = 0
    for d in open_drives:
        is_eligible, reasons = check_student_eligibility(student, d)
        if is_eligible:
            eligible_drives_count += 1
        drives_with_eligibility.append({
            "drive": d,
            "is_eligible": is_eligible,
            "reasons": reasons,
            "applied": False,
        })

    # Student's own applications
    my_applications = PlacementApplication.objects.filter(student=student).select_related(
        "placement_drive__company"
    ).order_by("-application_date")

    applied_drive_ids = set(my_applications.values_list("placement_drive_id", flat=True))
    for item in drives_with_eligibility:
        if item["drive"].id in applied_drive_ids:
            item["applied"] = True

    shortlisted_count = my_applications.filter(
        status__in=[PlacementApplication.STATUS_SHORTLISTED, PlacementApplication.STATUS_INTERVIEW]
    ).count()

    # Upcoming Interview Rounds
    my_interviews = (
        PlacementRound.objects.filter(application__student=student, scheduled_date__gte=today)
        .select_related("application__placement_drive__company")
        .order_by("scheduled_date", "start_time")
    )

    # Offers / Results
    my_results = PlacementResult.objects.filter(student=student, result="Selected").select_related("company", "placement_drive")

    # Profile
    profile, _ = StudentPlacementProfile.objects.get_or_create(student=student)

    return render(
        request,
        "placements/student_portal.html",
        {
            "student": student,
            "profile": profile,
            "drives_with_eligibility": drives_with_eligibility,
            "eligible_drives_count": eligible_drives_count,
            "my_applications": my_applications,
            "applied_count": my_applications.count(),
            "shortlisted_count": shortlisted_count,
            "my_interviews": my_interviews,
            "my_results": my_results,
            "offers_count": my_results.count(),
        },
    )


@login_required(login_url="/accounts/login/")
def student_apply_drive(request, pk):
    """
    Submits a placement application.
    Validates eligibility, deadlines, and duplicate prevention.
    """
    ctx_role = get_user_role(request.user)
    student = ctx_role["student"]
    if not student:
        return HttpResponseForbidden("Only students can apply to placement drives.")

    drive = get_object_or_404(PlacementDrive, pk=pk)

    # 1. Check duplicate application
    if PlacementApplication.objects.filter(student=student, placement_drive=drive).exists():
        messages.warning(request, f"You have already applied to {drive.company.name} for '{drive.job_title}'.")
        return redirect("drive_detail", pk=drive.pk)

    # 2. Check eligibility
    is_eligible, reasons = check_student_eligibility(student, drive)
    if not is_eligible:
        reason_msg = " ".join(reasons)
        messages.error(request, f"Cannot apply: {reason_msg}")
        return redirect("drive_detail", pk=drive.pk)

    profile, _ = StudentPlacementProfile.objects.get_or_create(student=student)

    if request.method == "POST":
        form = PlacementApplicationForm(request.POST, request.FILES)
        if form.is_valid():
            app = form.save(commit=False)
            app.student = student
            app.placement_drive = drive
            app.status = PlacementApplication.STATUS_APPLIED
            app.eligibility_status = True
            app.save()

            # Notify student
            notify_user(
                request.user,
                title="Placement Application Submitted",
                message=f"Your application for '{drive.job_title}' at {drive.company.name} has been received.",
                link=f"/placements/drives/{drive.pk}/",
            )

            messages.success(request, f"Application for '{drive.job_title}' at {drive.company.name} submitted successfully!")
            return redirect("student_placement_portal")
    else:
        # Pre-populate with default resume if available
        initial = {}
        if profile.default_resume:
            initial["resume"] = profile.default_resume
        form = PlacementApplicationForm(initial=initial)

    return render(
        request,
        "placements/apply_form.html",
        {
            "form": form,
            "drive": drive,
            "student": student,
            "profile": profile,
        },
    )


@login_required(login_url="/accounts/login/")
def student_history(request):
    """Full placement journey history for the logged in student."""
    ctx_role = get_user_role(request.user)
    student = ctx_role["student"]
    if not student:
        return redirect("placements_dashboard")

    applications = PlacementApplication.objects.filter(student=student).select_related(
        "placement_drive__company"
    ).order_by("-application_date")

    results = PlacementResult.objects.filter(student=student).select_related("company", "placement_drive")
    rounds = PlacementRound.objects.filter(application__student=student).select_related("application__placement_drive__company").order_by("-scheduled_date")

    return render(
        request,
        "placements/student_history.html",
        {
            "student": student,
            "applications": applications,
            "results": results,
            "rounds": rounds,
        },
    )


@login_required(login_url="/accounts/login/")
def student_profile_edit(request):
    """Allows student to update their placement resume, skills, and links."""
    ctx_role = get_user_role(request.user)
    student = ctx_role["student"]
    if not student:
        return HttpResponseForbidden("Student access required.")

    profile, _ = StudentPlacementProfile.objects.get_or_create(student=student)
    if request.method == "POST":
        form = StudentPlacementProfileForm(request.POST, request.FILES, instance=profile)
        if form.is_valid():
            form.save()
            messages.success(request, "Placement profile and default resume updated successfully.")
            return redirect("student_placement_portal")
    else:
        form = StudentPlacementProfileForm(instance=profile)

    return render(request, "placements/profile_form.html", {"form": form, "student": student})


# ============================================================
# 5. APPLICATION MANAGEMENT & INTERVIEW ROUNDS
# ============================================================

@login_required(login_url="/accounts/login/")
def application_list(request):
    """Officer view of all applications with multi-filter."""
    ctx_role = get_user_role(request.user)
    if not ctx_role["is_officer"]:
        return HttpResponseForbidden("Placement officer privileges required.")

    qs = PlacementApplication.objects.select_related(
        "student__course", "student__department", "placement_drive__company"
    ).order_by("-application_date")

    # Filters
    drive_id = request.GET.get("drive", "").strip()
    status_filter = request.GET.get("status", "").strip()
    course_id = request.GET.get("course", "").strip()
    year_val = request.GET.get("year", "").strip()
    search_q = request.GET.get("q", "").strip()

    if drive_id:
        qs = qs.filter(placement_drive_id=drive_id)
    if status_filter:
        qs = qs.filter(status=status_filter)
    if course_id:
        qs = qs.filter(student__course_id=course_id)
    if year_val:
        qs = qs.filter(student__year=year_val)
    if search_q:
        qs = qs.filter(
            Q(student__name__icontains=search_q)
            | Q(student__roll_no__icontains=search_q)
            | Q(placement_drive__company__name__icontains=search_q)
        )

    drives = PlacementDrive.objects.all().order_by("-drive_date")
    courses = Course.objects.all().order_by("name")

    return render(
        request,
        "placements/application_list.html",
        {
            "applications": qs,
            "drives": drives,
            "courses": courses,
            "selected_drive": drive_id,
            "status_filter": status_filter,
            "selected_course": course_id,
            "selected_year": year_val,
            "search_q": search_q,
            "status_choices": PlacementApplication.STATUS_CHOICES,
        },
    )


@login_required(login_url="/accounts/login/")
def application_detail(request, pk):
    """Application dossier, round history, and interview actions."""
    app = get_object_or_404(
        PlacementApplication.objects.select_related(
            "student__course", "student__department", "placement_drive__company"
        ),
        pk=pk,
    )
    ctx_role = get_user_role(request.user)

    # Security check: User must be student owner or placement officer
    is_owner = ctx_role["student"] and (app.student == ctx_role["student"])
    if not (is_owner or ctx_role["is_officer"]):
        return HttpResponseForbidden("You do not have permission to view this application.")

    rounds = app.rounds.all().order_by("round_number")
    result = PlacementResult.objects.filter(placement_drive=app.placement_drive, student=app.student).first()

    return render(
        request,
        "placements/application_detail.html",
        {
            "app": app,
            "student": app.student,
            "drive": app.placement_drive,
            "rounds": rounds,
            "result": result,
            "is_officer": ctx_role["is_officer"],
            "is_owner": is_owner,
        },
    )


@login_required(login_url="/accounts/login/")
def application_status_update(request, pk):
    """Officer quick updates application status (Shortlisted, Rejected, etc)."""
    if request.method != "POST":
        return redirect("application_detail", pk=pk)

    ctx_role = get_user_role(request.user)
    if not ctx_role["is_officer"]:
        return HttpResponseForbidden("Placement officer privileges required.")

    app = get_object_or_404(PlacementApplication, pk=pk)
    new_status = request.POST.get("status")
    remarks = request.POST.get("remarks", "").strip()

    if new_status in dict(PlacementApplication.STATUS_CHOICES):
        app.status = new_status
        if remarks:
            app.remarks = remarks
        app.save()

        # Notify student
        if app.student.user:
            notify_user(
                app.student.user,
                title=f"Application Update: {app.placement_drive.company.name}",
                message=f"Your application status for {app.placement_drive.job_title} was updated to '{new_status}'.",
                link=f"/placements/applications/{app.pk}/",
            )

        messages.success(request, f"Application for {app.student.name} updated to '{new_status}'.")

    return redirect("application_detail", pk=pk)


@login_required(login_url="/accounts/login/")
def round_create(request, application_id):
    """Officer schedules an interview / evaluation round for a candidate."""
    ctx_role = get_user_role(request.user)
    if not ctx_role["is_officer"]:
        return HttpResponseForbidden("Placement officer privileges required.")

    app = get_object_or_404(PlacementApplication, pk=application_id)

    if request.method == "POST":
        form = PlacementRoundForm(request.POST)
        if form.is_valid():
            round_obj = form.save(commit=False)
            round_obj.application = app
            round_obj.save()

            # Update application status to Interview Scheduled
            app.status = PlacementApplication.STATUS_INTERVIEW
            app.current_round = round_obj.round_name
            app.save()

            # Notify candidate
            if app.student.user:
                notify_user(
                    app.student.user,
                    title=f"Interview Scheduled: {app.placement_drive.company.name}",
                    message=f"{round_obj.round_name} scheduled on {round_obj.scheduled_date.strftime('%d %b %Y')} at {round_obj.start_time.strftime('%I:%M %p')}. Location: {round_obj.location}.",
                    link=f"/placements/applications/{app.pk}/",
                )

            messages.success(request, f"{round_obj.round_name} scheduled for {app.student.name}.")
            return redirect("application_detail", pk=app.pk)
    else:
        next_round_num = app.rounds.count() + 1
        form = PlacementRoundForm(initial={"round_number": next_round_num, "round_name": f"Round {next_round_num}"})

    return render(request, "placements/round_form.html", {"form": form, "app": app})


@login_required(login_url="/accounts/login/")
def round_update(request, pk):
    """Officer updates the round outcome and score."""
    ctx_role = get_user_role(request.user)
    if not ctx_role["is_officer"]:
        return HttpResponseForbidden("Placement officer privileges required.")

    round_obj = get_object_or_404(PlacementRound, pk=pk)
    app = round_obj.application

    if request.method == "POST":
        form = PlacementRoundForm(request.POST, instance=round_obj)
        if form.is_valid():
            form.save()

            # Notify candidate
            if app.student.user:
                notify_user(
                    app.student.user,
                    title=f"Round Result: {round_obj.round_name}",
                    message=f"Outcome for {round_obj.round_name} at {app.placement_drive.company.name}: {round_obj.result}.",
                    link=f"/placements/applications/{app.pk}/",
                )

            messages.success(request, f"Outcome for {round_obj.round_name} saved.")
            return redirect("application_detail", pk=app.pk)
    else:
        form = PlacementRoundForm(instance=round_obj)

    return render(request, "placements/round_form.html", {"form": form, "app": app, "round_obj": round_obj})


@login_required(login_url="/accounts/login/")
def result_create(request, application_id):
    """Officer records final placement decision and issues offer letter."""
    ctx_role = get_user_role(request.user)
    if not ctx_role["is_officer"]:
        return HttpResponseForbidden("Placement officer privileges required.")

    app = get_object_or_404(PlacementApplication, pk=application_id)

    if request.method == "POST":
        form = PlacementResultForm(request.POST, request.FILES)
        if form.is_valid():
            result_obj = form.save(commit=False)
            result_obj.student = app.student
            result_obj.company = app.placement_drive.company
            result_obj.placement_drive = app.placement_drive
            result_obj.save()

            # Update application status
            app.status = (
                PlacementApplication.STATUS_SELECTED
                if result_obj.result == "Selected"
                else PlacementApplication.STATUS_NOT_SELECTED
            )
            app.current_round = "Final Decision"
            app.save()

            # Send high priority congratulations notification
            if app.student.user:
                if result_obj.result == "Selected":
                    notify_user(
                        app.student.user,
                        title=f"CONGRATULATIONS! Selected at {result_obj.company.name}!",
                        message=f"You have been selected as {result_obj.job_title} at {result_obj.company.name} with CTC {result_obj.ctc}!",
                        link="/placements/student/",
                    )
                else:
                    notify_user(
                        app.student.user,
                        title=f"Placement Drive Update: {result_obj.company.name}",
                        message=f"Your final outcome for {result_obj.company.name} has been updated.",
                        link=f"/placements/applications/{app.pk}/",
                    )

            messages.success(request, f"Final decision for {app.student.name} recorded.")
            return redirect("application_detail", pk=app.pk)
    else:
        initial = {
            "job_title": app.placement_drive.job_title,
            "ctc": app.placement_drive.salary_package,
            "result": "Selected",
        }
        form = PlacementResultForm(initial=initial)

    return render(request, "placements/result_form.html", {"form": form, "app": app})


# ============================================================
# 6. SECURE DOCUMENT STREAMING
# ============================================================

@login_required(login_url="/accounts/login/")
def download_resume(request, pk):
    """Secure streaming for student resumes."""
    app = get_object_or_404(PlacementApplication, pk=pk)
    ctx_role = get_user_role(request.user)

    is_owner = ctx_role["student"] and (app.student == ctx_role["student"])
    if not (is_owner or ctx_role["is_officer"]):
        return HttpResponseForbidden("Unauthorized access to candidate resume.")

    if not app.resume:
        raise Http404("No resume uploaded.")

    file_path = app.resume.path
    if not os.path.exists(file_path):
        raise Http404("File could not be found.")

    filename = os.path.basename(file_path)
    response = FileResponse(open(file_path, "rb"))
    response["Content-Disposition"] = f'inline; filename="{filename}"'
    return response


@login_required(login_url="/accounts/login/")
def download_offer_letter(request, pk):
    """Secure streaming for job offer letters."""
    result = get_object_or_404(PlacementResult, pk=pk)
    ctx_role = get_user_role(request.user)

    is_owner = ctx_role["student"] and (result.student == ctx_role["student"])
    if not (is_owner or ctx_role["is_officer"]):
        return HttpResponseForbidden("Unauthorized access to offer letter.")

    if not result.offer_letter:
        raise Http404("No offer letter uploaded.")

    file_path = result.offer_letter.path
    if not os.path.exists(file_path):
        raise Http404("Offer letter file not found.")

    filename = os.path.basename(file_path)
    response = FileResponse(open(file_path, "rb"))
    response["Content-Disposition"] = f'inline; filename="{filename}"'
    return response
