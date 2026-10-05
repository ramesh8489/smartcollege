from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User

from students.models import Student, Department, Course
from faculty.models import Faculty, Subject
from attendance.models import Attendance
from marks.models import Marks
from timetable.models import Circular, SchoolIncharge, Timetable, FacultyLeaveRequest
from django.core.paginator import Paginator
from django.db.models import Count, Q
from urllib.parse import urlencode
from . import scope as sc


# ============================================================
# LOGIN
# ============================================================

def login_view(request):

    if request.method == "POST":

        username = request.POST.get("username")
        password = request.POST.get("password")

        user = authenticate(
            request,
            username=username,
            password=password
        )

        if user is not None:

            # ====================================================
            # STUDENT
            # ====================================================

            student = Student.objects.filter(
                user=user
            ).first()

            if student is not None:

                if not student.is_active:
                    return render(request, "accounts/login.html", {"error": "Your student account is inactive. Please contact the administrator."})

                if not student.is_approved:

                    return render(
                        request,
                        "accounts/login.html",
                        {
                            "error":
                                "Your student account is still "
                                "waiting for admin approval."
                        }
                    )

                login(request, user)
                return redirect("/students/")


            # ====================================================
            # FACULTY
            # ====================================================

            faculty = Faculty.objects.filter(
                user=user
            ).first() or Faculty.objects.filter(
                email=user.email
            ).first()

            if faculty is not None:

                if not faculty.is_active:
                    return render(request, "accounts/login.html", {"error": "Your faculty account is inactive. Please contact the administrator."})

                if not faculty.is_approved:

                    return render(
                        request,
                        "accounts/login.html",
                        {
                            "error":
                                "Your faculty account is still "
                                "waiting for admin approval."
                        }
                    )

                login(request, user)
                return redirect("/faculty/")


            # ====================================================
            # ADMIN
            # ====================================================

            if user.is_superuser:

                login(request, user)

                return redirect(
                    "/accounts/admin-dashboard/"
                )


            # ====================================================
            # UNKNOWN USER
            # ====================================================

            login(request, user)

            return redirect(
                "/accounts/login/"
            )


        # ========================================================
        # INVALID LOGIN
        # ========================================================

        return render(
            request,
            "accounts/login.html",
            {
                "error":
                    "Invalid username or password"
            }
        )


    return render(
        request,
        "accounts/login.html"
    )


# ============================================================
# LOGOUT
# ============================================================

def logout_view(request):

    logout(request)

    return redirect(
        "/accounts/login/"
    )


# ============================================================
# REGISTER
# ============================================================

def register_view(request):

    tree = [
        {
            "id": d.id,
            "name": d.name,
            "courses": [
                {"id": c.id, "name": c.name}
                for c in sorted(d.courses.all(), key=lambda c: c.name)
            ],
        }
        for d in Department.objects.order_by("name").prefetch_related("courses")
    ]

    if request.method == "POST":

        role = request.POST.get("role")
        name = request.POST.get("name", "").strip()
        email = request.POST.get("email", "").strip()
        username = request.POST.get("username", "").strip()
        password = request.POST.get("password", "")
        confirm_password = request.POST.get("confirm_password", "")
        department_id = request.POST.get("department")
        course_id = request.POST.get("course", "").strip()
        roll_no = request.POST.get("roll_no", "").strip()
        sif_number = request.POST.get("sif_number", "").strip()
        year = request.POST.get("year", "").strip()
        faculty_id = request.POST.get("faculty_id", "").strip()

        error = None

        if not all([role, name, email, username, password, confirm_password, department_id]):
            error = "Please fill in all fields."

        elif role not in ("student", "faculty"):
            error = "Please select whether you are a student or faculty."

        elif password != confirm_password:
            error = "Passwords do not match."

        elif len(password) < 6:
            error = "Password must be at least 6 characters."

        elif User.objects.filter(username=username).exists():
            error = "That username is already taken."

        elif role == "student" and not (roll_no and year and sif_number):
            error = "Please fill in your SIF number, roll number and year."

        elif role == "student" and not course_id:
            error = "Please select your course."

        elif role == "student" and Student.objects.filter(roll_no=roll_no).exists():
            error = "That roll number is already registered."

        elif role == "student" and Student.objects.filter(sif_number=sif_number).exists():
            error = "That SIF number is already registered."

        elif role == "faculty" and not faculty_id:
            error = "Please fill in your faculty ID."

        elif role == "faculty" and Faculty.objects.filter(faculty_id=faculty_id).exists():
            error = "That faculty ID is already registered."

        if error:

            return render(
                request,
                "accounts/register.html",
                {
                    "error": error,
                    "tree": tree,
                    "values": request.POST,
                }
            )

        department = Department.objects.get(id=department_id)

        course = Course.objects.filter(id=course_id).first() if course_id else None

        if role == "student" and course is not None and str(course.department_id) != str(department_id):
            return render(
                request,
                "accounts/register.html",
                {
                    "error": "Selected course does not belong to the selected school.",
                    "tree": tree,
                    "values": request.POST,
                }
            )

        user = User.objects.create(
            username=username,
            email=email,
        )
        user.set_password(password)
        user.save()

        if role == "student":

            Student.objects.create(
                user=user,
                name=name,
                roll_no=roll_no,
                sif_number=sif_number,
                email=email,
                department=department,
                course=course,
                year=int(year),
                is_approved=False,
            )

        else:

            Faculty.objects.create(
                user=user,
                name=name,
                faculty_id=faculty_id,
                email=email,
                department=department,
                is_approved=False,
            )

        return render(
            request,
            "accounts/register.html",
            {
                "success":
                    "Registration submitted! An admin needs to "
                    "approve your account before you can log in.",
                "tree": tree,
            }
        )

    return render(
        request,
        "accounts/register.html",
        {
            "tree": tree,
        }
    )


@login_required(login_url="/accounts/login/")
def mark_leave_seen(request, leave_id):

    if not request.user.is_superuser:
        return redirect("/accounts/login/")

    FacultyLeaveRequest.objects.filter(
        id=leave_id,
        forwarded_to_admin=True,
    ).update(
        admin_seen=True
    )

    return redirect("/accounts/admin-dashboard/?tab=leave_messages")


# ============================================================
# APPROVE / REJECT (admin only)
# ============================================================

@login_required(login_url="/accounts/login/")
def approve_student(request, student_id):

    if not request.user.is_superuser:
        return redirect("/accounts/login/")

    student = Student.objects.filter(id=student_id).first()

    if student is not None:
        student.is_approved = True
        student.save()

    return redirect("/accounts/admin-dashboard/?tab=approvals")


@login_required(login_url="/accounts/login/")
def reject_student(request, student_id):

    if not request.user.is_superuser:
        return redirect("/accounts/login/")

    student = Student.objects.filter(id=student_id).first()

    if student is not None:
        user = student.user
        student.delete()
        if user is not None:
            user.delete()

    return redirect("/accounts/admin-dashboard/?tab=approvals")


@login_required(login_url="/accounts/login/")
def approve_faculty(request, faculty_id):

    if not request.user.is_superuser:
        return redirect("/accounts/login/")

    faculty = Faculty.objects.filter(id=faculty_id).first()

    if faculty is not None:
        faculty.is_approved = True
        faculty.save()

    return redirect("/accounts/admin-dashboard/?tab=approvals")


@login_required(login_url="/accounts/login/")
def reject_faculty(request, faculty_id):

    if not request.user.is_superuser:
        return redirect("/accounts/login/")

    faculty = Faculty.objects.filter(id=faculty_id).first()

    if faculty is not None:
        user = faculty.user
        faculty.delete()
        if user is not None:
            user.delete()

    return redirect("/accounts/admin-dashboard/?tab=approvals")


# ============================================================
# ADMIN DASHBOARD  (School -> Degree -> Class drill-down)
# ============================================================

ADMIN_TABS = ("overview", "students", "faculty", "approvals", "leave_messages", "circulars")


def _dash_url(**params):

    clean = {k: v for k, v in params.items() if v not in (None, "")}

    return "/accounts/admin-dashboard/?" + urlencode(clean)


def _meter_class(value):

    if value is None:
        return ""

    if value >= 75:
        return "good"

    if value >= 60:
        return "mid"

    return "low"


@login_required(login_url="/accounts/login/")
def admin_dashboard(request):

    if not request.user.is_superuser:
        return redirect("/accounts/login/")

    tab = request.GET.get("tab", "overview")

    if tab not in ADMIN_TABS:
        tab = "overview"

    scope = sc.parse_scope(request.GET)
    level = scope["level"]

    school, course, year = scope["school"], scope["course"], scope["year"]

    students_qs = sc.scoped_students(scope)
    faculty_qs = sc.scoped_faculty(scope)

    tree = sc.filter_tree()

    # Keep the active filters when moving between tabs / drilling down
    keep = {
        "school": school.id if school else None,
        "course": course.id if course else None,
        "year": year,
    }

    pending_students = Student.objects.filter(
        is_approved=False
    ).select_related("department", "course").order_by("-id")

    pending_faculty = Faculty.objects.filter(
        is_approved=False
    ).select_related("department").order_by("-id")

    context = {
        "tab": tab,
        "scope": scope,
        "level": level,
        "tree": tree,
        "keep": keep,
        "pending_count": pending_students.count() + pending_faculty.count(),
        "tab_urls": {
            name: _dash_url(tab=name, **keep) for name in ADMIN_TABS
        },
        "reset_url": _dash_url(tab=tab),
    }

    # Breadcrumb  All schools > School > Degree > Class
    crumbs = [{"label": "All schools", "url": _dash_url(tab=tab)}]

    if school:
        crumbs.append({"label": school.name, "url": _dash_url(tab=tab, school=school.id)})

    if course:
        crumbs.append({"label": course.name, "url": _dash_url(tab=tab, school=school.id, course=course.id)})

    if year:
        crumbs.append({"label": f"Year {year}", "url": None})

    context["crumbs"] = crumbs


    # ==========================================================
    # OVERVIEW
    # ==========================================================

    if tab == "overview":

        stats = sc.overall_stats(students_qs)

        class_pairs = (
            students_qs.filter(course__isnull=False)
            .values("course_id", "year").distinct().count()
        )

        degrees_in_scope = (
            students_qs.filter(course__isnull=False)
            .values("course_id").distinct().count()
        )

        context["cards"] = {
            "students": students_qs.count(),
            "faculty": faculty_qs.count(),
            "degrees": degrees_in_scope,
            "classes": class_pairs,
            "attendance_pct": stats["attendance_pct"],
            "attendance_cls": _meter_class(stats["attendance_pct"]),
            "marks_pct": stats["marks_pct"],
            "marks_cls": _meter_class(stats["marks_pct"]),
        }

        rows = []

        # ---------------- level: all schools ----------------
        if level == "all":

            student_counts = dict(
                students_qs.values_list("department_id").annotate(n=Count("id"))
            )
            faculty_counts = dict(
                faculty_qs.values_list("department_id").annotate(n=Count("id"))
            )
            course_counts = dict(
                Course.objects.values_list("department_id").annotate(n=Count("id"))
            )
            incharges = {
                i.department_id: i.faculty.name
                for i in SchoolIncharge.objects.select_related("faculty")
            }
            gs = sc.grouped_stats(students_qs, "student__department_id")

            for dept in Department.objects.order_by("name"):
                g = gs.get(dept.id, {})
                rows.append({
                    "name": dept.name,
                    "url": _dash_url(tab="overview", school=dept.id),
                    "students": student_counts.get(dept.id, 0),
                    "faculty": faculty_counts.get(dept.id, 0),
                    "extra": (
                        f"{course_counts.get(dept.id, 0)} "
                        f"degree{'' if course_counts.get(dept.id, 0) == 1 else 's'}"
                    ),
                    "incharge": incharges.get(dept.id),
                    "attendance_pct": g.get("attendance_pct"),
                    "attendance_cls": _meter_class(g.get("attendance_pct")),
                    "marks_pct": g.get("marks_pct"),
                    "marks_cls": _meter_class(g.get("marks_pct")),
                })

            context["breakdown_title"] = "Schools"
            context["breakdown_hint"] = "Pick a school to see its degrees."
            context["first_col"] = "School"
            context["extra_col"] = "Degrees"

        # ---------------- level: one school -> degrees ----------------
        elif level == "school":

            student_counts = dict(
                students_qs.values_list("course_id").annotate(n=Count("id"))
            )
            gs = sc.grouped_stats(students_qs, "student__course_id")

            years_by_course = {
                c["id"]: c["years"]
                for d in tree if d["id"] == school.id
                for c in d["courses"]
            }

            for c in school.courses.order_by("name"):
                g = gs.get(c.id, {})
                yrs = years_by_course.get(c.id, [])
                rows.append({
                    "name": c.name,
                    "url": _dash_url(tab="overview", school=school.id, course=c.id),
                    "students": student_counts.get(c.id, 0),
                    "faculty": None,
                    "extra": f"{len(yrs)} class{'es' if len(yrs) != 1 else ''}",
                    "attendance_pct": g.get("attendance_pct"),
                    "attendance_cls": _meter_class(g.get("attendance_pct")),
                    "marks_pct": g.get("marks_pct"),
                    "marks_cls": _meter_class(g.get("marks_pct")),
                })

            context["breakdown_title"] = f"Degrees in {school.name}"
            context["breakdown_hint"] = "Pick a degree to see its classes."
            context["first_col"] = "Degree"
            context["extra_col"] = "Classes"
            context["school_incharge"] = (
                SchoolIncharge.objects.select_related("faculty")
                .filter(department=school).first()
            )

        # ---------------- level: one degree -> classes (years) ----------------
        elif level == "course":

            student_counts = dict(
                students_qs.values_list("year").annotate(n=Count("id"))
            )
            gs = sc.grouped_stats(students_qs, "student__year")

            faculty_by_year = {}

            for cls_year, fac_id in Timetable.objects.filter(
                school_class__course=course
            ).values_list("school_class__year", "faculty_id").distinct():
                faculty_by_year.setdefault(cls_year, set()).add(fac_id)

            years = next(
                (c["years"] for d in tree for c in d["courses"] if c["id"] == course.id),
                [],
            )

            for y in years:
                g = gs.get(y, {})
                rows.append({
                    "name": f"Year {y}",
                    "url": _dash_url(tab="overview", school=school.id, course=course.id, year=y),
                    "students": student_counts.get(y, 0),
                    "faculty": len(faculty_by_year.get(y, ())),
                    "extra": None,
                    "attendance_pct": g.get("attendance_pct"),
                    "attendance_cls": _meter_class(g.get("attendance_pct")),
                    "marks_pct": g.get("marks_pct"),
                    "marks_cls": _meter_class(g.get("marks_pct")),
                })

            context["breakdown_title"] = f"Classes in {course.name}"
            context["breakdown_hint"] = "Pick a class to see its students and timetable."
            context["first_col"] = "Class"
            context["extra_col"] = None

        # ---------------- level: one class ----------------
        else:

            class_students = list(students_qs.order_by("name"))
            st = sc.per_student_stats([s_.id for s_ in class_students])

            context["class_students"] = [
                {
                    "obj": s_,
                    "attendance_pct": st[s_.id]["attendance_pct"],
                    "attendance_cls": _meter_class(st[s_.id]["attendance_pct"]),
                    "marks_pct": st[s_.id]["marks_pct"],
                    "marks_cls": _meter_class(st[s_.id]["marks_pct"]),
                }
                for s_ in class_students
            ]

            context["timetable"] = sc.class_timetable(course, year)

            context["class_faculty"] = (
                Faculty.objects.filter(
                    id__in=Timetable.objects.filter(
                        school_class__course=course,
                        school_class__year=year,
                    ).values("faculty_id")
                )
            )

        context["rows"] = rows


    # ==========================================================
    # STUDENTS TAB (search + pagination)
    # ==========================================================

    elif tab == "students":

        q = request.GET.get("q", "").strip()

        qs = students_qs.order_by("name")

        if q:
            qs = qs.filter(
                Q(name__icontains=q)
                | Q(roll_no__icontains=q)
                | Q(sif_number__icontains=q)
                | Q(email__icontains=q)
            )

        paginator = Paginator(qs, 20)
        page = paginator.get_page(request.GET.get("page"))

        st = sc.per_student_stats([s_.id for s_ in page])

        context["q"] = q
        context["page"] = page
        context["student_rows"] = [
            {
                "obj": s_,
                "attendance_pct": st[s_.id]["attendance_pct"],
                "attendance_cls": _meter_class(st[s_.id]["attendance_pct"]),
                "marks_pct": st[s_.id]["marks_pct"],
                "marks_cls": _meter_class(st[s_.id]["marks_pct"]),
            }
            for s_ in page
        ]

        base = {k: v for k, v in keep.items() if v}
        if q:
            base["q"] = q

        context["page_base"] = urlencode({"tab": "students", **base})
        context["export_url"] = "/reports/admin/students/excel/?" + urlencode(base)


    # ==========================================================
    # FACULTY TAB
    # ==========================================================

    elif tab == "faculty":

        q = request.GET.get("q", "").strip()

        qs = faculty_qs.order_by("name")

        if q:
            qs = qs.filter(
                Q(name__icontains=q)
                | Q(faculty_id__icontains=q)
                | Q(email__icontains=q)
            )

        incharge_map = {
            i.faculty_id: i.department.name
            for i in SchoolIncharge.objects.select_related("department")
        }

        slot_counts = dict(
            Timetable.objects.values_list("faculty_id").annotate(n=Count("id"))
        )

        subject_names = {}

        for fid, sname in Subject.objects.values_list("faculty_id", "name"):
            subject_names.setdefault(fid, []).append(sname)

        context["q"] = q
        context["faculty_rows"] = [
            {
                "obj": f,
                "subjects": subject_names.get(f.id, []),
                "slots": slot_counts.get(f.id, 0),
                "incharge_of": incharge_map.get(f.id),
            }
            for f in qs
        ]


    # ==========================================================
    # APPROVALS TAB
    # ==========================================================

    elif tab == "approvals":

        context["pending_students"] = pending_students
        context["pending_faculty"] = pending_faculty


    # ==========================================================
    # LEAVE MESSAGES TAB
    # ==========================================================

    elif tab == "leave_messages":

        context["leave_requests"] = FacultyLeaveRequest.objects.filter(
            forwarded_to_admin=True
        ).select_related(
            "faculty",
            "department",
            "reviewed_by",
        )

        context["unseen_leave_count"] = FacultyLeaveRequest.objects.filter(
            forwarded_to_admin=True,
            admin_seen=False,
        ).count()


    # ==========================================================
    # STUDENT LEAVES TAB
    # ==========================================================

    elif tab == "student_leaves":
        from student_leave.models import StudentLeaveRequest
        sl_qs = StudentLeaveRequest.objects.select_related("student__course", "student__department").order_by("-applied_date")

        sl_type = request.GET.get("leave_type", "").strip()
        sl_status = request.GET.get("status", "").strip()
        sl_q = request.GET.get("q", "").strip()

        if school:
            sl_qs = sl_qs.filter(student__department=school)
        if course:
            sl_qs = sl_qs.filter(student__course=course)
        if year:
            sl_qs = sl_qs.filter(student__year=year)
        if sl_type:
            sl_qs = sl_qs.filter(leave_type=sl_type)
        if sl_status:
            sl_qs = sl_qs.filter(status=sl_status)
        if sl_q:
            sl_qs = sl_qs.filter(Q(student__name__icontains=sl_q) | Q(student__roll_no__icontains=sl_q))

        paginator = Paginator(sl_qs, 20)
        context["student_leaves_page"] = paginator.get_page(request.GET.get("page"))
        context["sl_type"] = sl_type
        context["sl_status"] = sl_status
        context["sl_q"] = sl_q
        context["leave_types"] = StudentLeaveRequest.LEAVE_TYPE_CHOICES
        context["status_choices"] = StudentLeaveRequest.STATUS_CHOICES


    # ==========================================================
    # CIRCULARS TAB
    # ==========================================================

    elif tab == "circulars":

        context["circulars"] = Circular.objects.all()[:30]


    # Institutional Student Leaves Overview Stats
    from student_leave.models import StudentLeaveRequest
    all_admin_leaves = StudentLeaveRequest.objects.all()
    context["student_leaves_total_count"] = all_admin_leaves.count()
    context["student_leaves_pending_count"] = all_admin_leaves.filter(
        status__in=[
            StudentLeaveRequest.STATUS_PENDING,
            StudentLeaveRequest.STATUS_FACULTY_APPROVED,
            StudentLeaveRequest.STATUS_INCHARGE_APPROVED,
        ]
    ).count()
    context["student_leaves_approved_count"] = all_admin_leaves.filter(
        status=StudentLeaveRequest.STATUS_ADMIN_APPROVED
    ).count()
    context["student_leaves_rejected_count"] = all_admin_leaves.filter(
        status__in=[
            StudentLeaveRequest.STATUS_FACULTY_REJECTED,
            StudentLeaveRequest.STATUS_INCHARGE_REJECTED,
            StudentLeaveRequest.STATUS_ADMIN_REJECTED,
        ]
    ).count()
    context["student_leaves_recent"] = all_admin_leaves.select_related("student__course", "student__department").order_by("-applied_date")[:5]

    # Training & Placement Institutional Stats
    from placements.models import Company, PlacementDrive, PlacementApplication, PlacementResult
    context["placement_companies_count"] = Company.objects.filter(status=Company.STATUS_ACTIVE).count()
    context["placement_drives_count"] = PlacementDrive.objects.count()
    context["placement_apps_count"] = PlacementApplication.objects.count()
    context["placement_placed_count"] = PlacementResult.objects.filter(result="Selected").values("student").distinct().count()
    context["placement_recent_drives"] = PlacementDrive.objects.select_related("company").order_by("-created_at")[:5]

    # Certificate & Document Management Institutional Stats
    from certificates.models import CertificateRequest, StudentDocument, GeneratedCertificate
    context["cert_stats"] = {
        "total_requests": CertificateRequest.objects.count(),
        "pending_requests": CertificateRequest.objects.filter(status=CertificateRequest.STATUS_PENDING).count(),
        "approved_requests": CertificateRequest.objects.filter(status=CertificateRequest.STATUS_APPROVED).count(),
        "generated_certs": GeneratedCertificate.objects.count(),
        "pending_docs": StudentDocument.objects.filter(verification_status=StudentDocument.STATUS_PENDING).count(),
    }

    return render(
        request,
        "accounts/admin_dashboard.html",
        context
    )
