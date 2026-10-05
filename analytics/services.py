import datetime
from decimal import Decimal
from django.db.models import (
    Count, Avg, Sum, Min, Max, Q, F, Case, When, Value, IntegerField, DecimalField
)
from django.utils import timezone

from students.models import Student, Department, Course
from faculty.models import Faculty, Subject
from attendance.models import Attendance
from marks.models import Marks
from timetable.models import Timetable, SchoolClass, Period, SchoolIncharge, FacultyLeaveRequest
from fees.models import FeeRecord, FeePayment
from library.models import Book, BookLoan
from exams.models import Exam, ExamSchedule, StudentExamMark
from assignments.models import Assignment, AssignmentSubmission
from student_leave.models import StudentLeaveRequest
from placements.models import Company, PlacementDrive, StudentPlacementProfile, PlacementApplication
from certificates.models import CertificateRequest, CertificateType, StudentDocument, GeneratedCertificate
from .models import AnalyticsSetting


def _int_or_none(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def get_analytics_scope(user, params):
    """
    Identifies the requesting user's role and permission scope:
    - admin: Superuser or staff with college-wide visibility.
    - school_incharge: Faculty assigned as School Incharge; strictly restricted to their department.
    - faculty: Faculty member; restricted to their assigned subjects/classes/students.
    - student: Enrolled student; restricted strictly to their own profile and records.

    Parses filter parameters safely while enforcing hard security boundaries.
    """
    if not user or not user.is_authenticated:
        return None

    is_admin = user.is_superuser or user.is_staff
    student = Student.objects.filter(user=user).first()
    faculty = Faculty.objects.filter(user=user).first() or Faculty.objects.filter(email=user.email).first()
    incharge = SchoolIncharge.objects.select_related("department", "faculty").filter(faculty=faculty).first() if faculty else None

    # Role resolution
    if student and not is_admin:
        role = "student"
    elif incharge and not is_admin:
        role = "school_incharge"
    elif faculty and not is_admin:
        role = "faculty"
    elif is_admin:
        role = "admin"
    else:
        role = "student" if student else "admin"

    # Extract filter parameters
    raw_school = _int_or_none(params.get("school"))
    raw_course = _int_or_none(params.get("course"))
    raw_year = _int_or_none(params.get("year"))
    raw_sem = _int_or_none(params.get("semester"))
    raw_subject = _int_or_none(params.get("subject"))
    date_from_str = params.get("date_from", "").strip()
    date_to_str = params.get("date_to", "").strip()
    risk_filter = params.get("risk_level", "").strip()
    search_q = params.get("q", "").strip()

    date_from = None
    date_to = None
    if date_from_str:
        try:
            date_from = datetime.datetime.strptime(date_from_str, "%Y-%m-%d").date()
        except ValueError:
            date_from = None
    if date_to_str:
        try:
            date_to = datetime.datetime.strptime(date_to_str, "%Y-%m-%d").date()
        except ValueError:
            date_to = None

    # Hard security enforcement per role
    school = None
    course = None
    year = raw_year if raw_year in [1, 2, 3, 4] else None
    semester = raw_sem if raw_sem in range(1, 9) else None
    subject = None

    if role == "school_incharge":
        # School Incharge CANNOT change school. It is fixed to their assigned department.
        school = incharge.department
    elif role == "faculty":
        school = faculty.department
    elif role == "admin":
        if raw_school:
            school = Department.objects.filter(id=raw_school).first()

    # Course validation within school
    if raw_course:
        course_cand = Course.objects.select_related("department").filter(id=raw_course).first()
        if course_cand:
            if school:
                if course_cand.department_id == school.id:
                    course = course_cand
            else:
                course = course_cand
                school = course_cand.department

    # Subject validation
    if raw_subject:
        subj_qs = Subject.objects.select_related("department", "faculty")
        if role == "faculty":
            subj_qs = subj_qs.filter(faculty=faculty)
        elif school:
            subj_qs = subj_qs.filter(department=school)
        subject = subj_qs.filter(id=raw_subject).first()

    # Dropdown lists for UI filters
    if role == "school_incharge":
        available_schools = Department.objects.filter(id=incharge.department_id)
        available_courses = Course.objects.filter(department=incharge.department)
        available_subjects = Subject.objects.filter(department=incharge.department)
    elif role == "faculty":
        available_schools = Department.objects.filter(id=faculty.department_id)
        available_courses = Course.objects.filter(department=faculty.department)
        available_subjects = Subject.objects.filter(faculty=faculty)
    else:
        available_schools = Department.objects.all().order_by("name")
        if school:
            available_courses = Course.objects.filter(department=school).order_by("name")
            available_subjects = Subject.objects.filter(department=school).order_by("name")
        else:
            available_courses = Course.objects.all().order_by("name")
            available_subjects = Subject.objects.all().order_by("name")

    settings = AnalyticsSetting.get_settings()

    return {
        "role": role,
        "user": user,
        "is_admin": is_admin,
        "student": student,
        "faculty": faculty,
        "incharge": incharge,
        "school": school,
        "course": course,
        "year": year,
        "semester": semester,
        "subject": subject,
        "date_from": date_from,
        "date_to": date_to,
        "date_from_str": date_from_str if date_from else "",
        "date_to_str": date_to_str if date_to else "",
        "risk_level": risk_filter if risk_filter in ["High", "Medium", "Low", "Critical", "Warning", "Safe"] else "",
        "q": search_q,
        "is_restricted_school": (role == "school_incharge"),
        "available_schools": available_schools,
        "available_courses": available_courses,
        "available_years": [1, 2, 3, 4],
        "available_semesters": [1, 2, 3, 4, 5, 6, 7, 8],
        "available_subjects": available_subjects,
        "settings": settings,
        "generated_at": timezone.now(),
    }


def scoped_students(scope):
    """Returns the Student queryset matching the current security scope and filters."""
    qs = Student.objects.select_related("department", "course").filter(is_active=True)

    if scope["role"] == "student" and scope["student"]:
        return qs.filter(id=scope["student"].id)

    if scope["role"] == "faculty" and scope["faculty"]:
        # Students in classes or subjects taught by faculty
        faculty_subjects = Subject.objects.filter(faculty=scope["faculty"])
        faculty_classes = Timetable.objects.filter(faculty=scope["faculty"]).values_list("school_class", flat=True)
        # Students either taking those subjects via attendance/marks or enrolled in classes
        student_ids_from_attendance = Attendance.objects.filter(subject__in=faculty_subjects).values_list("student_id", flat=True)
        student_ids_from_marks = Marks.objects.filter(subject__in=faculty_subjects).values_list("student_id", flat=True)
        student_ids_from_classes = set()
        for sc in SchoolClass.objects.filter(id__in=faculty_classes):
            student_ids_from_classes.update(Student.objects.filter(course=sc.course, year=sc.year).values_list("id", flat=True))

        combined_ids = set(student_ids_from_attendance) | set(student_ids_from_marks) | student_ids_from_classes
        if combined_ids:
            qs = qs.filter(Q(id__in=combined_ids) | Q(department=scope["faculty"].department))
        else:
            qs = qs.filter(department=scope["faculty"].department)

    if scope["school"]:
        qs = qs.filter(department=scope["school"])
    if scope["course"]:
        qs = qs.filter(course=scope["course"])
    if scope["year"]:
        qs = qs.filter(year=scope["year"])

    if scope["q"]:
        q = scope["q"]
        qs = qs.filter(
            Q(name__icontains=q) |
            Q(roll_no__icontains=q) |
            Q(email__icontains=q) |
            Q(sif_number__icontains=q)
        )

    return qs


def scoped_faculty(scope):
    """Returns the Faculty queryset matching the current scope and filters."""
    qs = Faculty.objects.select_related("department").filter(is_active=True)

    if scope["role"] == "faculty" and scope["faculty"]:
        return qs.filter(id=scope["faculty"].id)

    if scope["school"]:
        qs = qs.filter(department=scope["school"])

    if scope["q"]:
        q = scope["q"]
        qs = qs.filter(
            Q(name__icontains=q) |
            Q(faculty_id__icontains=q) |
            Q(email__icontains=q) |
            Q(designation__icontains=q)
        )

    return qs


def scoped_attendance(scope):
    """Returns the Attendance queryset matching the scope and filters."""
    students = scoped_students(scope)
    qs = Attendance.objects.filter(student__in=students).select_related("student", "subject", "subject__department")

    if scope["subject"]:
        qs = qs.filter(subject=scope["subject"])
    elif scope["role"] == "faculty" and scope["faculty"]:
        qs = qs.filter(subject__faculty=scope["faculty"])

    if scope["date_from"]:
        qs = qs.filter(date__gte=scope["date_from"])
    if scope["date_to"]:
        qs = qs.filter(date__lte=scope["date_to"])

    return qs


def scoped_marks(scope):
    """Returns the internal Marks queryset matching scope and filters."""
    students = scoped_students(scope)
    qs = Marks.objects.filter(student__in=students).select_related("student", "subject", "subject__department")

    if scope["subject"]:
        qs = qs.filter(subject=scope["subject"])
    elif scope["role"] == "faculty" and scope["faculty"]:
        qs = qs.filter(subject__faculty=scope["faculty"])

    return qs


def scoped_exam_marks(scope):
    """Returns the StudentExamMark queryset matching scope and filters."""
    students = scoped_students(scope)
    qs = StudentExamMark.objects.filter(student__in=students).select_related("student", "exam", "subject")

    if scope["subject"]:
        qs = qs.filter(subject=scope["subject"])
    elif scope["role"] == "faculty" and scope["faculty"]:
        qs = qs.filter(subject__faculty=scope["faculty"])

    if scope["date_from"]:
        qs = qs.filter(exam__start_date__gte=scope["date_from"])
    if scope["date_to"]:
        qs = qs.filter(exam__end_date__lte=scope["date_to"])

    return qs


# ==============================================================================
# KPI & SUMMARY METRICS
# ==============================================================================

def get_kpi_summary(scope):
    """Computes high-level cross-module summary statistics using database aggregation."""
    students_qs = scoped_students(scope)
    faculty_qs = scoped_faculty(scope)
    att_qs = scoped_attendance(scope)
    marks_qs = scoped_marks(scope)
    exam_marks_qs = scoped_exam_marks(scope)

    total_students = students_qs.count()
    total_faculty = faculty_qs.count()

    # Subjects & Classes in scope
    if scope["school"]:
        total_subjects = Subject.objects.filter(department=scope["school"]).count()
        total_classes = SchoolClass.objects.filter(department=scope["school"]).count()
    else:
        total_subjects = Subject.objects.count()
        total_classes = SchoolClass.objects.count()

    # Attendance overall
    att_agg = att_qs.aggregate(
        total=Count("id"),
        present=Count(Case(When(present=True, then=1), output_field=IntegerField()))
    )
    att_total = att_agg["total"] or 0
    att_present = att_agg["present"] or 0
    avg_attendance = round((att_present / att_total) * 100, 1) if att_total > 0 else None

    # Academic Marks overall
    marks_count = marks_qs.count()
    exam_marks_count = exam_marks_qs.count()
    avg_marks = None

    if exam_marks_count > 0:
        avg_pct = exam_marks_qs.aggregate(avg=Avg("percentage"))["avg"]
        if avg_pct is not None:
            avg_marks = round(float(avg_pct), 1)
    elif marks_count > 0:
        # Max grand total is 150 (3 CATs x 40 + 3 assignments x 10)
        marks_agg = marks_qs.aggregate(
            avg_gt=Avg(F("cat_1") + F("cat_2") + F("cat_3") + F("cat_1_assignment") + F("cat_2_assignment") + F("cat_3_assignment"))
        )
        if marks_agg["avg_gt"] is not None:
            avg_marks = round((float(marks_agg["avg_gt"]) / 150.0) * 100, 1)

    # Fees in scope
    fee_records_qs = FeeRecord.objects.filter(student__in=students_qs)
    fees_total = fee_records_qs.aggregate(total=Sum("amount"))["total"] or Decimal("0.00")
    fees_collected = FeePayment.objects.filter(fee_record__in=fee_records_qs).aggregate(paid=Sum("amount"))["paid"] or Decimal("0.00")
    fees_outstanding = max(fees_total - fees_collected, Decimal("0.00"))
    fee_collection_rate = round((float(fees_collected) / float(fees_total)) * 100, 1) if fees_total > 0 else 0.0

    # Library
    loans_in_scope = BookLoan.objects.filter(student__in=students_qs)
    books_issued_count = loans_in_scope.filter(return_date__isnull=True).count()

    # Placements
    eligible_students_count = students_qs.filter(year__gte=3).count() if not scope["year"] else students_qs.count()
    placed_count = PlacementApplication.objects.filter(
        student__in=students_qs, status=PlacementApplication.STATUS_SELECTED
    ).values("student").distinct().count()
    placement_rate = round((placed_count / eligible_students_count) * 100, 1) if eligible_students_count > 0 else 0.0

    # Certificates & Documents
    pending_cert_requests = CertificateRequest.objects.filter(
        student__in=students_qs, status=CertificateRequest.STATUS_PENDING
    ).count()
    pending_doc_verification = StudentDocument.objects.filter(
        student__in=students_qs, verification_status=StudentDocument.STATUS_PENDING
    ).count()

    return {
        "total_students": total_students,
        "total_faculty": total_faculty,
        "total_subjects": total_subjects,
        "total_classes": total_classes,
        "avg_attendance": avg_attendance,
        "avg_marks": avg_marks,
        "fees_total": fees_total,
        "fees_collected": fees_collected,
        "fees_outstanding": fees_outstanding,
        "fee_collection_rate": fee_collection_rate,
        "books_issued": books_issued_count,
        "placement_rate": placement_rate,
        "eligible_students_count": eligible_students_count,
        "placed_students_count": placed_count,
        "pending_certificates": pending_cert_requests,
        "pending_doc_verification": pending_doc_verification,
    }


# ==============================================================================
# STUDENT PERFORMANCE & ACADEMIC ANALYTICS
# ==============================================================================

def get_academic_analytics(scope):
    """
    Computes subject-wise, course-wise, year-wise, and student performance metrics
    using real marks and exam records.
    """
    students_qs = scoped_students(scope)
    marks_qs = scoped_marks(scope)
    exam_marks_qs = scoped_exam_marks(scope)

    # 1. Subject-wise average performance
    # Combine exam marks and internal marks
    subjects_data = []
    all_subjects = Subject.objects.filter(
        id__in=set(marks_qs.values_list("subject_id", flat=True)) |
               set(exam_marks_qs.values_list("subject_id", flat=True))
    ).select_related("department", "faculty")

    for subj in all_subjects:
        em_sub = exam_marks_qs.filter(subject=subj)
        m_sub = marks_qs.filter(subject=subj)

        avg_pct = None
        count_students = 0
        pass_count = 0
        fail_count = 0
        max_score = 0.0
        min_score = 100.0

        if em_sub.exists():
            em_agg = em_sub.aggregate(
                avg=Avg("percentage"),
                total=Count("id"),
                p_cnt=Count(Case(When(result_status="Pass", then=1), output_field=IntegerField())),
                f_cnt=Count(Case(When(result_status="Fail", then=1), output_field=IntegerField())),
                mx=Max("percentage"),
                mn=Min("percentage")
            )
            avg_pct = round(float(em_agg["avg"]), 1) if em_agg["avg"] is not None else None
            count_students = em_agg["total"] or 0
            pass_count = em_agg["p_cnt"] or 0
            fail_count = em_agg["f_cnt"] or 0
            max_score = round(float(em_agg["mx"]), 1) if em_agg["mx"] is not None else 0.0
            min_score = round(float(em_agg["mn"]), 1) if em_agg["mn"] is not None else 0.0
        elif m_sub.exists():
            m_agg = m_sub.aggregate(
                avg_gt=Avg(F("cat_1") + F("cat_2") + F("cat_3") + F("cat_1_assignment") + F("cat_2_assignment") + F("cat_3_assignment")),
                total=Count("id"),
                mx=Max(F("cat_1") + F("cat_2") + F("cat_3") + F("cat_1_assignment") + F("cat_2_assignment") + F("cat_3_assignment")),
                mn=Min(F("cat_1") + F("cat_2") + F("cat_3") + F("cat_1_assignment") + F("cat_2_assignment") + F("cat_3_assignment"))
            )
            if m_agg["avg_gt"] is not None:
                avg_pct = round((float(m_agg["avg_gt"]) / 150.0) * 100, 1)
            count_students = m_agg["total"] or 0
            pass_threshold = scope["settings"].marks_passing_threshold
            for rec in m_sub:
                rec_pct = (rec.grand_total / 150.0) * 100
                if rec_pct >= float(pass_threshold):
                    pass_count += 1
                else:
                    fail_count += 1
            max_score = round((float(m_agg["mx"]) / 150.0) * 100, 1) if m_agg["mx"] is not None else 0.0
            min_score = round((float(m_agg["mn"]) / 150.0) * 100, 1) if m_agg["mn"] is not None else 0.0

        if avg_pct is not None:
            pass_rate = round((pass_count / count_students) * 100, 1) if count_students > 0 else 0.0
            subjects_data.append({
                "subject": subj,
                "name": subj.name,
                "code": subj.code,
                "faculty_name": subj.faculty.name if subj.faculty else "Unassigned",
                "students_count": count_students,
                "avg_percentage": avg_pct,
                "pass_rate": pass_rate,
                "fail_count": fail_count,
                "max_score": max_score,
                "min_score": min_score,
            })

    subjects_data.sort(key=lambda x: x["avg_percentage"], reverse=True)

    # 2. Course-wise average marks
    course_data = []
    courses = Course.objects.filter(id__in=students_qs.values_list("course_id", flat=True)).distinct().select_related("department")
    for crs in courses:
        crs_students = students_qs.filter(course=crs)
        em_crs = exam_marks_qs.filter(student__in=crs_students)
        m_crs = marks_qs.filter(student__in=crs_students)

        avg_pct = None
        if em_crs.exists():
            avg_val = em_crs.aggregate(avg=Avg("percentage"))["avg"]
            if avg_val is not None:
                avg_pct = round(float(avg_val), 1)
        elif m_crs.exists():
            avg_val = m_crs.aggregate(
                avg_gt=Avg(F("cat_1") + F("cat_2") + F("cat_3") + F("cat_1_assignment") + F("cat_2_assignment") + F("cat_3_assignment"))
            )["avg_gt"]
            if avg_val is not None:
                avg_pct = round((float(avg_val) / 150.0) * 100, 1)

        course_data.append({
            "course": crs,
            "name": crs.name,
            "department": crs.department.name,
            "student_count": crs_students.count(),
            "avg_percentage": avg_pct,
        })
    course_data.sort(key=lambda x: (x["avg_percentage"] is not None, x["avg_percentage"]), reverse=True)

    # 3. Year-wise average marks
    year_data = []
    for yr in [1, 2, 3, 4]:
        yr_students = students_qs.filter(year=yr)
        if not yr_students.exists():
            continue
        em_yr = exam_marks_qs.filter(student__in=yr_students)
        m_yr = marks_qs.filter(student__in=yr_students)

        avg_pct = None
        if em_yr.exists():
            avg_val = em_yr.aggregate(avg=Avg("percentage"))["avg"]
            if avg_val is not None:
                avg_pct = round(float(avg_val), 1)
        elif m_yr.exists():
            avg_val = m_yr.aggregate(
                avg_gt=Avg(F("cat_1") + F("cat_2") + F("cat_3") + F("cat_1_assignment") + F("cat_2_assignment") + F("cat_3_assignment"))
            )["avg_gt"]
            if avg_val is not None:
                avg_pct = round((float(avg_val) / 150.0) * 100, 1)

        year_data.append({
            "year": yr,
            "year_label": f"Year {yr}",
            "student_count": yr_students.count(),
            "avg_percentage": avg_pct,
        })

    # 4. Student Ranking: Top performers & lowest performers
    student_perf_list = []
    for st in students_qs:
        em_st = exam_marks_qs.filter(student=st)
        m_st = marks_qs.filter(student=st)

        avg_pct = None
        eval_count = 0
        if em_st.exists():
            avg_val = em_st.aggregate(avg=Avg("percentage"))["avg"]
            eval_count = em_st.count()
            if avg_val is not None:
                avg_pct = round(float(avg_val), 1)
        elif m_st.exists():
            avg_val = m_st.aggregate(
                avg_gt=Avg(F("cat_1") + F("cat_2") + F("cat_3") + F("cat_1_assignment") + F("cat_2_assignment") + F("cat_3_assignment"))
            )["avg_gt"]
            eval_count = m_st.count()
            if avg_val is not None:
                avg_pct = round((float(avg_val) / 150.0) * 100, 1)

        if avg_pct is not None:
            student_perf_list.append({
                "student": st,
                "name": st.name,
                "roll_no": st.roll_no,
                "course": st.course.name if st.course else "—",
                "year": st.year,
                "eval_count": eval_count,
                "avg_percentage": avg_pct,
            })

    student_perf_list.sort(key=lambda x: x["avg_percentage"], reverse=True)
    top_performers = student_perf_list[:5]
    lowest_performers = list(reversed(student_perf_list[-5:])) if student_perf_list else []

    # 5. Performance Distribution Categories
    dist_threshold = float(scope["settings"].marks_distinction_threshold)
    pass_threshold = float(scope["settings"].marks_passing_threshold)

    dist_counts = {
        "distinction": 0,  # >= 75%
        "first_class": 0,  # 60% - 74.99%
        "second_class": 0, # 50% - 59.99%
        "pass_class": 0,   # 40% - 49.99%
        "fail_class": 0,   # < 40%
    }
    for item in student_perf_list:
        p = item["avg_percentage"]
        if p >= dist_threshold:
            dist_counts["distinction"] += 1
        elif p >= 60.0:
            dist_counts["first_class"] += 1
        elif p >= 50.0:
            dist_counts["second_class"] += 1
        elif p >= pass_threshold:
            dist_counts["pass_class"] += 1
        else:
            dist_counts["fail_class"] += 1

    return {
        "subjects": subjects_data,
        "courses": course_data,
        "years": year_data,
        "top_performers": top_performers,
        "lowest_performers": lowest_performers,
        "distribution": dist_counts,
        "total_evaluated_students": len(student_perf_list),
    }


# ==============================================================================
# ATTENDANCE ANALYTICS
# ==============================================================================

def get_attendance_analytics(scope):
    """
    Computes detailed attendance breakdown:
    - Overall attendance statistics
    - Shortage categories (Safe >= 75%, Warning 65%–74.99%, Critical < 65%)
    - Course-wise, Year-wise, Subject-wise, Faculty-wise breakdown
    - Attendance Risk List with filters
    """
    students_qs = scoped_students(scope)
    att_qs = scoped_attendance(scope)
    settings = scope["settings"]
    warn_threshold = float(settings.attendance_warning_threshold)
    crit_threshold = float(settings.attendance_critical_threshold)

    # Overall counters
    total_records = att_qs.count()
    present_records = att_qs.filter(present=True).count()
    absent_records = total_records - present_records
    overall_pct = round((present_records / total_records) * 100, 1) if total_records > 0 else None

    # Student-wise attendance evaluation
    risk_list = []
    safe_count = 0
    warning_count = 0
    critical_count = 0

    for st in students_qs:
        st_att = att_qs.filter(student=st)
        tot = st_att.count()
        pres = st_att.filter(present=True).count()
        abs_count = tot - pres
        pct = round((pres / tot) * 100, 1) if tot > 0 else None

        if pct is None:
            risk_level = "No Data"
            badge_class = "gray"
        elif pct >= warn_threshold:
            risk_level = "Safe"
            badge_class = "green"
            safe_count += 1
        elif pct >= crit_threshold:
            risk_level = "Warning"
            badge_class = "amber"
            warning_count += 1
        else:
            risk_level = "Critical"
            badge_class = "rose"
            critical_count += 1

        # Apply risk filter if requested
        if scope["risk_level"] and scope["risk_level"] != risk_level:
            continue

        risk_list.append({
            "student": st,
            "name": st.name,
            "roll_no": st.roll_no,
            "course": st.course.name if st.course else "—",
            "year": st.year,
            "department": st.department.name,
            "total_classes": tot,
            "present_count": pres,
            "absent_count": abs_count,
            "attendance_pct": pct,
            "risk_level": risk_level,
            "badge_class": badge_class,
        })

    # Sort risk list by percentage ascending (critical first)
    risk_list.sort(key=lambda x: (x["attendance_pct"] is None, x["attendance_pct"] if x["attendance_pct"] is not None else 999))

    # Subject-wise attendance
    subject_attendance = []
    subjects_in_scope = Subject.objects.filter(
        id__in=att_qs.values_list("subject_id", flat=True)
    ).distinct().select_related("faculty", "department")

    for subj in subjects_in_scope:
        s_att = att_qs.filter(subject=subj)
        s_tot = s_att.count()
        s_pres = s_att.filter(present=True).count()
        s_pct = round((s_pres / s_tot) * 100, 1) if s_tot > 0 else 0.0

        subject_attendance.append({
            "subject": subj,
            "name": subj.name,
            "code": subj.code,
            "faculty": subj.faculty.name if subj.faculty else "Unassigned",
            "total_records": s_tot,
            "present_count": s_pres,
            "attendance_pct": s_pct,
        })
    subject_attendance.sort(key=lambda x: x["attendance_pct"], reverse=True)

    # Course-wise attendance
    course_attendance = []
    courses = Course.objects.filter(id__in=students_qs.values_list("course_id", flat=True)).distinct()
    for crs in courses:
        c_students = students_qs.filter(course=crs)
        c_att = att_qs.filter(student__in=c_students)
        c_tot = c_att.count()
        c_pres = c_att.filter(present=True).count()
        c_pct = round((c_pres / c_tot) * 100, 1) if c_tot > 0 else None

        course_attendance.append({
            "course": crs,
            "name": crs.name,
            "total_records": c_tot,
            "attendance_pct": c_pct,
        })
    course_attendance.sort(key=lambda x: (x["attendance_pct"] is not None, x["attendance_pct"]), reverse=True)

    # Year-wise attendance
    year_attendance = []
    for yr in [1, 2, 3, 4]:
        y_students = students_qs.filter(year=yr)
        if not y_students.exists():
            continue
        y_att = att_qs.filter(student__in=y_students)
        y_tot = y_att.count()
        y_pres = y_att.filter(present=True).count()
        y_pct = round((y_pres / y_tot) * 100, 1) if y_tot > 0 else None

        year_attendance.append({
            "year": yr,
            "year_label": f"Year {yr}",
            "total_records": y_tot,
            "attendance_pct": y_pct,
        })

    # Faculty-wise attendance sessions
    faculty_attendance = []
    faculty_members = Faculty.objects.filter(
        id__in=att_qs.values_list("subject__faculty_id", flat=True)
    ).distinct()
    for f in faculty_members:
        f_att = att_qs.filter(subject__faculty=f)
        f_tot = f_att.count()
        f_pres = f_att.filter(present=True).count()
        f_pct = round((f_pres / f_tot) * 100, 1) if f_tot > 0 else None

        faculty_attendance.append({
            "faculty": f,
            "name": f.name,
            "designation": f.designation,
            "total_records": f_tot,
            "attendance_pct": f_pct,
        })
    faculty_attendance.sort(key=lambda x: (x["attendance_pct"] is not None, x["attendance_pct"]), reverse=True)

    return {
        "overall_percentage": overall_pct,
        "total_records": total_records,
        "present_count": present_records,
        "absent_count": absent_records,
        "safe_count": safe_count,
        "warning_count": warning_count,
        "critical_count": critical_count,
        "risk_list": risk_list,
        "subject_attendance": subject_attendance,
        "course_attendance": course_attendance,
        "year_attendance": year_attendance,
        "faculty_attendance": faculty_attendance,
        "warn_threshold": warn_threshold,
        "crit_threshold": crit_threshold,
    }


# ==============================================================================
# AT-RISK STUDENT IDENTIFICATION (ACADEMIC RISK INDICATOR)
# ==============================================================================

def get_risk_student_analytics(scope):
    """
    Transparent rule-based scoring engine for identifying students needing academic attention.
    Scoring:
    - Attendance Risk (40% weight):
      * < 65% critical shortage: 40 pts
      * 65%–74.99% warning: 25 pts
      * >= 75%: 0 pts
    - Academic Marks Risk (40% weight):
      * Average marks < 40% (Fail): 40 pts
      * Average marks 40%–49.99%: 20 pts
      * Has failed subjects: +15 pts
    - Auxiliary Indicators (20% weight):
      * Outstanding fee balance: 10 pts
      * Overdue library books: 5 pts
      * Missing/overdue assignments: 5 pts

    Total Score: 0 to 100.
    Level: High (>=60), Medium (30–59), Low (<30).
    Provides itemized transparent reasons.
    """
    students_qs = scoped_students(scope)
    att_qs = scoped_attendance(scope)
    marks_qs = scoped_marks(scope)
    exam_marks_qs = scoped_exam_marks(scope)
    settings = scope["settings"]

    warn_threshold = float(settings.attendance_warning_threshold)
    crit_threshold = float(settings.attendance_critical_threshold)
    pass_threshold = float(settings.marks_passing_threshold)

    today = timezone.localdate()
    students_data = []

    high_risk_count = 0
    medium_risk_count = 0
    low_risk_count = 0

    for st in students_qs:
        score = 0
        reasons = []

        # 1. Attendance Evaluation
        st_att = att_qs.filter(student=st)
        att_tot = st_att.count()
        att_pres = st_att.filter(present=True).count()
        att_pct = round((att_pres / att_tot) * 100, 1) if att_tot > 0 else None

        if att_pct is not None:
            if att_pct < crit_threshold:
                score += 40
                reasons.append(f"Attendance critical: {att_pct}% (Below {crit_threshold}% threshold)")
            elif att_pct < warn_threshold:
                score += 25
                reasons.append(f"Attendance warning: {att_pct}% (Below {warn_threshold}% safe requirement)")
        else:
            reasons.append("No attendance records logged yet")

        # 2. Academic Marks Evaluation
        em_st = exam_marks_qs.filter(student=st)
        m_st = marks_qs.filter(student=st)

        marks_pct = None
        failed_count = 0

        if em_st.exists():
            avg_val = em_st.aggregate(avg=Avg("percentage"))["avg"]
            if avg_val is not None:
                marks_pct = round(float(avg_val), 1)
            failed_count = em_st.filter(result_status="Fail").count()
        elif m_st.exists():
            avg_val = m_st.aggregate(
                avg_gt=Avg(F("cat_1") + F("cat_2") + F("cat_3") + F("cat_1_assignment") + F("cat_2_assignment") + F("cat_3_assignment"))
            )["avg_gt"]
            if avg_val is not None:
                marks_pct = round((float(avg_val) / 150.0) * 100, 1)
            for m in m_st:
                if (m.grand_total / 150.0) * 100 < pass_threshold:
                    failed_count += 1

        if marks_pct is not None:
            if marks_pct < pass_threshold:
                score += 40
                reasons.append(f"Academic score critical: {marks_pct}% (Below passing {pass_threshold}%)")
            elif marks_pct < 50.0:
                score += 20
                reasons.append(f"Marginal academic score: {marks_pct}% (Average below 50%)")

            if failed_count > 0:
                score += 15
                reasons.append(f"Failed in {failed_count} subject(s)")
        else:
            reasons.append("No exam or CAT marks recorded yet")

        # 3. Auxiliary: Outstanding Fees
        st_fees = FeeRecord.objects.filter(student=st)
        total_fee = st_fees.aggregate(tot=Sum("amount"))["tot"] or Decimal("0.00")
        paid_fee = FeePayment.objects.filter(fee_record__in=st_fees).aggregate(pd=Sum("amount"))["pd"] or Decimal("0.00")
        bal_fee = max(total_fee - paid_fee, Decimal("0.00"))

        if bal_fee > Decimal("0.00"):
            score += 10
            reasons.append(f"Outstanding fee balance: ₹{bal_fee:,.2f}")

        # 4. Auxiliary: Overdue Library Loans
        overdue_books = BookLoan.objects.filter(
            student=st, return_date__isnull=True, due_date__lt=today
        ).count()
        if overdue_books > 0:
            score += 5
            reasons.append(f"{overdue_books} library book loan(s) overdue")

        # 5. Auxiliary: Pending/Missing Assignments
        if st.course:
            course_assignments = Assignment.objects.filter(
                course=st.course, year=st.year, is_active=True
            )
            submitted_assignment_ids = AssignmentSubmission.objects.filter(
                student=st, assignment__in=course_assignments
            ).values_list("assignment_id", flat=True)
            missing_assignments = course_assignments.exclude(id__in=submitted_assignment_ids).count()
            if missing_assignments > 0:
                score += 5
                reasons.append(f"{missing_assignments} pending coursework assignment(s)")

        # Cap score at 100
        score = min(score, 100)

        # Categorize
        if score >= 60:
            risk_level = "High"
            badge_class = "rose"
            high_risk_count += 1
        elif score >= 30:
            risk_level = "Medium"
            badge_class = "amber"
            medium_risk_count += 1
        else:
            risk_level = "Low"
            badge_class = "green"
            low_risk_count += 1

        # Filter by risk level if selected
        if scope["risk_level"] and scope["risk_level"] != risk_level:
            continue

        students_data.append({
            "student": st,
            "name": st.name,
            "roll_no": st.roll_no,
            "course": st.course.name if st.course else "—",
            "year": st.year,
            "department": st.department.name,
            "attendance_pct": att_pct,
            "marks_pct": marks_pct,
            "fee_balance": bal_fee,
            "risk_score": score,
            "risk_level": risk_level,
            "badge_class": badge_class,
            "reasons": reasons,
        })

    # Sort descending by risk score
    students_data.sort(key=lambda x: x["risk_score"], reverse=True)

    return {
        "students": students_data,
        "high_risk_count": high_risk_count,
        "medium_risk_count": medium_risk_count,
        "low_risk_count": low_risk_count,
        "total_evaluated": len(students_data),
    }


# ==============================================================================
# AI-STYLE ACADEMIC INSIGHTS GENERATOR
# ==============================================================================

def get_ai_insights(scope, kpi, academic, attendance, risk):
    """
    Transparent rule-based intelligence generator that synthesizes genuine database insights.
    Does NOT output fake statements or randomized placeholders.
    """
    insights = []

    # 1. Attendance Shortage Insight
    crit_count = attendance.get("critical_count", 0)
    total_att_students = len(attendance.get("risk_list", []))
    if crit_count > 0:
        insights.append({
            "type": "danger",
            "icon": "clock",
            "title": "Critical Attendance Alert",
            "message": f"{crit_count} of {total_att_students} students have attendance below {attendance['crit_threshold']}%, which constitutes a critical shortage.",
            "metric": f"{crit_count} Critical Students",
        })
    elif attendance.get("overall_percentage") is not None:
        insights.append({
            "type": "success",
            "icon": "check",
            "title": "Healthy Attendance Trend",
            "message": f"Overall attendance across sessions is maintaining a healthy average of {attendance['overall_percentage']}%.",
            "metric": f"{attendance['overall_percentage']}% Attendance",
        })

    # 2. Subject Performance Insights
    subjects = academic.get("subjects", [])
    if len(subjects) >= 2:
        lowest_subj = subjects[-1]
        highest_subj = subjects[0]
        insights.append({
            "type": "warning",
            "icon": "chart",
            "title": "Curriculum Focus Area",
            "message": f"'{lowest_subj['name']}' currently has the lowest average mark ({lowest_subj['avg_percentage']}%) among evaluated subjects.",
            "metric": f"{lowest_subj['avg_percentage']}% Avg",
        })
        insights.append({
            "type": "success",
            "icon": "award",
            "title": "Academic Subject Leader",
            "message": f"'{highest_subj['name']}' leads overall academic performance with a {highest_subj['avg_percentage']}% average.",
            "metric": f"{highest_subj['avg_percentage']}% Avg",
        })
    elif len(subjects) == 1:
        s = subjects[0]
        insights.append({
            "type": "info",
            "icon": "chart",
            "title": "Subject Performance Summary",
            "message": f"'{s['name']}' holds an average score of {s['avg_percentage']}% across enrolled candidates.",
            "metric": f"{s['avg_percentage']}% Avg",
        })

    # 3. Year-wise comparison insight
    years = academic.get("years", [])
    if len(years) >= 2:
        y_sorted = sorted(years, key=lambda x: (x["avg_percentage"] is not None, x["avg_percentage"]), reverse=True)
        top_y = y_sorted[0]
        bot_y = y_sorted[-1]
        if top_y["avg_percentage"] is not None and bot_y["avg_percentage"] is not None:
            insights.append({
                "type": "info",
                "icon": "layers",
                "title": "Cross-Year Comparison",
                "message": f"{top_y['year_label']} is leading academic achievement ({top_y['avg_percentage']}%) compared to {bot_y['year_label']} ({bot_y['avg_percentage']}%).",
                "metric": f"+{round(top_y['avg_percentage'] - bot_y['avg_percentage'], 1)}% Difference",
            })

    # 4. Academic Support Need
    high_risk = risk.get("high_risk_count", 0)
    med_risk = risk.get("medium_risk_count", 0)
    if high_risk > 0:
        insights.append({
            "type": "danger",
            "icon": "shield",
            "title": "Academic Support Recommendation",
            "message": f"{high_risk} student(s) have been flagged with High Academic Risk indicators requiring prompt mentoring and intervention.",
            "metric": f"{high_risk} High Risk Flagged",
        })
    elif med_risk > 0:
        insights.append({
            "type": "warning",
            "icon": "shield",
            "title": "Academic Mentoring Advisory",
            "message": f"{med_risk} student(s) display moderate performance or attendance variances that warrant faculty advisory.",
            "metric": f"{med_risk} Moderate Risks",
        })
    else:
        insights.append({
            "type": "success",
            "icon": "check",
            "title": "Positive Academic Standing",
            "message": "All enrolled candidates are currently meeting baseline academic and attendance benchmarks.",
            "metric": "0 High Risks",
        })

    # 5. Financial Collection Insight
    if kpi["fees_total"] > 0:
        col_rate = kpi["fee_collection_rate"]
        insights.append({
            "type": "info" if col_rate >= 50 else "warning",
            "icon": "file",
            "title": "Fee Collection Progress",
            "message": f"₹{kpi['fees_collected']:,.2f} of ₹{kpi['fees_total']:,.2f} total fees collected ({col_rate}%). Outstanding: ₹{kpi['fees_outstanding']:,.2f}.",
            "metric": f"{col_rate}% Collected",
        })

    # 6. Library Resource Utilization
    loans = BookLoan.objects.filter(student__in=scoped_students(scope))
    if loans.exists():
        top_book = loans.values("book__title").annotate(cnt=Count("id")).order_by("-cnt").first()
        if top_book:
            insights.append({
                "type": "info",
                "icon": "book",
                "title": "Library Circulation Trend",
                "message": f"'{top_book['book__title']}' is currently the most requested book resource with {top_book['cnt']} recorded loan(s).",
                "metric": f"{top_book['cnt']} Loan(s)",
            })

    return insights


# ==============================================================================
# FACULTY ANALYTICS & WORKLOAD
# ==============================================================================

def get_faculty_analytics(scope):
    """
    Computes faculty workload metrics:
    - Weekly periods from Timetable
    - Assigned subjects count
    - Students handled count
    - Attendance records taken
    - Average student marks in their subjects
    """
    faculty_qs = scoped_faculty(scope)
    total_faculty = faculty_qs.count()
    active_faculty = faculty_qs.filter(is_active=True).count()

    # Breakdown by designation
    by_designation = faculty_qs.values("designation").annotate(count=Count("id")).order_by("-count")

    # Breakdown by school
    by_school = faculty_qs.values("department__name").annotate(count=Count("id")).order_by("-count")

    workload_table = []
    for f in faculty_qs:
        f_subjects = Subject.objects.filter(faculty=f)
        subj_count = f_subjects.count()
        subj_names = list(f_subjects.values_list("name", flat=True))

        # Weekly teaching periods from Timetable
        weekly_periods = Timetable.objects.filter(faculty=f).count()

        # Attendance taken by this faculty
        attendance_taken = Attendance.objects.filter(subject__faculty=f).count()

        # Students handled (distinct students taking their subjects or enrolled in their timetable classes)
        handled_students_att = Attendance.objects.filter(subject__faculty=f).values_list("student_id", flat=True)
        handled_students_marks = Marks.objects.filter(subject__faculty=f).values_list("student_id", flat=True)
        classes_ids = Timetable.objects.filter(faculty=f).values_list("school_class_id", flat=True)
        handled_students_classes = set()
        for sc in SchoolClass.objects.filter(id__in=classes_ids):
            handled_students_classes.update(Student.objects.filter(course=sc.course, year=sc.year).values_list("id", flat=True))
        total_students_handled = len(set(handled_students_att) | set(handled_students_marks) | handled_students_classes)

        # Student average marks in their subjects
        em_f = StudentExamMark.objects.filter(subject__faculty=f)
        m_f = Marks.objects.filter(subject__faculty=f)
        avg_student_perf = None

        if em_f.exists():
            avg_val = em_f.aggregate(avg=Avg("percentage"))["avg"]
            if avg_val is not None:
                avg_student_perf = round(float(avg_val), 1)
        elif m_f.exists():
            avg_val = m_f.aggregate(
                avg_gt=Avg(F("cat_1") + F("cat_2") + F("cat_3") + F("cat_1_assignment") + F("cat_2_assignment") + F("cat_3_assignment"))
            )["avg_gt"]
            if avg_val is not None:
                avg_student_perf = round((float(avg_val) / 150.0) * 100, 1)

        workload_table.append({
            "faculty": f,
            "name": f.name,
            "faculty_id": f.faculty_id,
            "designation": f.designation,
            "department": f.department.name,
            "subjects_count": subj_count,
            "subjects_names": subj_names,
            "weekly_periods": weekly_periods,
            "students_handled": total_students_handled,
            "attendance_taken": attendance_taken,
            "avg_student_performance": avg_student_perf,
        })

    workload_table.sort(key=lambda x: x["weekly_periods"], reverse=True)

    return {
        "total_faculty": total_faculty,
        "active_faculty": active_faculty,
        "by_designation": by_designation,
        "by_school": by_school,
        "workload_table": workload_table,
    }


# ==============================================================================
# FEES ANALYTICS
# ==============================================================================

def get_fees_analytics(scope):
    """
    Computes fees collection, balances, fee types, and outstanding fee lists.
    """
    students_qs = scoped_students(scope)
    fee_records = FeeRecord.objects.filter(student__in=students_qs).select_related("student", "student__course")

    total_fees = fee_records.aggregate(total=Sum("amount"))["total"] or Decimal("0.00")
    total_paid = FeePayment.objects.filter(fee_record__in=fee_records).aggregate(paid=Sum("amount"))["paid"] or Decimal("0.00")
    total_outstanding = max(total_fees - total_paid, Decimal("0.00"))
    collection_percentage = round((float(total_paid) / float(total_fees)) * 100, 1) if total_fees > 0 else 0.0

    count_paid = fee_records.filter(status="PAID").count()
    count_partial = fee_records.filter(status="PARTIAL").count()
    count_unpaid = fee_records.filter(status="PENDING").count()

    # Fee type distribution
    type_dist = []
    for code, label in FeeRecord.FEE_TYPE_CHOICES:
        recs = fee_records.filter(fee_type=code)
        if recs.exists():
            t_tot = recs.aggregate(s=Sum("amount"))["s"] or Decimal("0.00")
            t_paid = FeePayment.objects.filter(fee_record__in=recs).aggregate(s=Sum("amount"))["s"] or Decimal("0.00")
            type_dist.append({
                "code": code,
                "label": label,
                "count": recs.count(),
                "total_amount": float(t_tot),
                "paid_amount": float(t_paid),
                "outstanding": float(max(t_tot - t_paid, Decimal("0.00"))),
            })

    # Course-wise fee collection
    course_fee_dist = []
    courses = Course.objects.filter(id__in=students_qs.values_list("course_id", flat=True)).distinct()
    for crs in courses:
        c_students = students_qs.filter(course=crs)
        c_recs = fee_records.filter(student__in=c_students)
        if c_recs.exists():
            c_tot = c_recs.aggregate(s=Sum("amount"))["s"] or Decimal("0.00")
            c_pd = FeePayment.objects.filter(fee_record__in=c_recs).aggregate(s=Sum("amount"))["s"] or Decimal("0.00")
            course_fee_dist.append({
                "course_name": crs.name,
                "total": float(c_tot),
                "paid": float(c_pd),
                "balance": float(max(c_tot - c_pd, Decimal("0.00"))),
            })

    # Fee Risk List (students with outstanding balance)
    fee_risk_list = []
    for rec in fee_records:
        bal = rec.balance_amount
        if bal > Decimal("0.00"):
            fee_risk_list.append({
                "record": rec,
                "student_name": rec.student.name,
                "roll_no": rec.student.roll_no,
                "course": rec.student.course.name if rec.student.course else "—",
                "year": rec.student.year,
                "title": rec.title,
                "fee_type": rec.get_fee_type_display(),
                "total_amount": rec.amount,
                "paid_amount": rec.paid_amount,
                "balance_amount": bal,
                "status": rec.status,
                "due_date": rec.due_date,
            })

    fee_risk_list.sort(key=lambda x: x["balance_amount"], reverse=True)

    return {
        "total_fees": total_fees,
        "total_paid": total_paid,
        "total_outstanding": total_outstanding,
        "collection_percentage": collection_percentage,
        "count_paid": count_paid,
        "count_partial": count_partial,
        "count_unpaid": count_unpaid,
        "type_distribution": type_dist,
        "course_distribution": course_fee_dist,
        "fee_risk_list": fee_risk_list,
    }


# ==============================================================================
# LIBRARY ANALYTICS
# ==============================================================================

def get_library_analytics(scope):
    """
    Computes library catalog and circulation analytics.
    """
    students_qs = scoped_students(scope)
    loans_qs = BookLoan.objects.filter(student__in=students_qs).select_related("book", "student")

    total_titles = Book.objects.count()
    book_copies = Book.objects.aggregate(
        total=Sum("total_copies"),
        available=Sum("available_copies")
    )
    total_copies = book_copies["total"] or 0
    available_copies = book_copies["available"] or 0
    issued_copies = max(total_copies - available_copies, 0)

    active_loans = loans_qs.filter(return_date__isnull=True).count()
    returned_loans = loans_qs.filter(return_date__isnull=False).count()
    today = timezone.localdate()
    overdue_loans_qs = loans_qs.filter(return_date__isnull=True, due_date__lt=today)
    overdue_count = overdue_loans_qs.count()
    total_fines = loans_qs.aggregate(s=Sum("fine_amount"))["s"] or Decimal("0.00")

    # Most issued books
    most_issued = loans_qs.values("book__title", "book__author").annotate(
        times_borrowed=Count("id")
    ).order_by("-times_borrowed")[:5]

    # Most active student borrowers
    most_active_borrowers = loans_qs.values(
        "student__name", "student__roll_no"
    ).annotate(
        total_loans=Count("id")
    ).order_by("-total_loans")[:5]

    # Category breakdown
    category_dist = []
    for cat_code, cat_label in Book.CATEGORY_CHOICES:
        cnt = Book.objects.filter(category=cat_code).count()
        if cnt > 0:
            category_dist.append({"label": cat_label, "count": cnt})

    # Overdue list
    overdue_list = []
    for l in overdue_loans_qs:
        overdue_list.append({
            "book_title": l.book.title,
            "student_name": l.student.name,
            "roll_no": l.student.roll_no,
            "due_date": l.due_date,
            "days_overdue": (today - l.due_date).days if l.due_date else 0,
            "calculated_fine": l.calculated_fine,
        })

    return {
        "total_titles": total_titles,
        "total_copies": total_copies,
        "available_copies": available_copies,
        "issued_copies": issued_copies,
        "active_loans": active_loans,
        "returned_loans": returned_loans,
        "overdue_count": overdue_count,
        "total_fines": total_fines,
        "most_issued": most_issued,
        "most_active_borrowers": most_active_borrowers,
        "category_distribution": category_dist,
        "overdue_list": overdue_list,
    }


# ==============================================================================
# PLACEMENT ANALYTICS
# ==============================================================================

def get_placement_analytics(scope):
    """
    Computes recruitment and career placement analytics with graceful empty states.
    """
    students_qs = scoped_students(scope)
    eligible_students = students_qs.filter(year__gte=3) if not scope["year"] else students_qs
    eligible_count = eligible_students.count()

    profiles_count = StudentPlacementProfile.objects.filter(student__in=students_qs).count()
    applications_qs = PlacementApplication.objects.filter(student__in=students_qs).select_related(
        "student", "placement_drive", "placement_drive__company"
    )
    total_applications = applications_qs.count()
    shortlisted_count = applications_qs.filter(
        status__in=[PlacementApplication.STATUS_SHORTLISTED, PlacementApplication.STATUS_INTERVIEW]
    ).count()
    selected_count = applications_qs.filter(status=PlacementApplication.STATUS_SELECTED).count()

    total_companies = Company.objects.count()
    total_drives = PlacementDrive.objects.count()

    placement_rate = round((selected_count / eligible_count) * 100, 1) if eligible_count > 0 else 0.0

    # Company-wise selections
    company_selections = []
    if applications_qs.exists():
        company_selections = applications_qs.filter(
            status=PlacementApplication.STATUS_SELECTED
        ).values("placement_drive__company__name").annotate(
            placed=Count("id")
        ).order_by("-placed")[:5]

    return {
        "has_data": (total_applications > 0 or profiles_count > 0 or total_drives > 0),
        "eligible_students": eligible_count,
        "registered_students": profiles_count,
        "students_applied": total_applications,
        "students_shortlisted": shortlisted_count,
        "students_selected": selected_count,
        "total_companies": total_companies,
        "total_drives": total_drives,
        "placement_rate": placement_rate,
        "company_selections": company_selections,
    }


# ==============================================================================
# CERTIFICATE & DOCUMENT ANALYTICS
# ==============================================================================

def get_certificate_analytics(scope):
    """
    Computes certificate request lifecycle and student verification metrics.
    """
    students_qs = scoped_students(scope)
    requests_qs = CertificateRequest.objects.filter(student__in=students_qs)
    docs_qs = StudentDocument.objects.filter(student__in=students_qs)

    total_requests = requests_qs.count()
    pending_count = requests_qs.filter(status=CertificateRequest.STATUS_PENDING).count()
    under_review_count = requests_qs.filter(status=CertificateRequest.STATUS_UNDER_REVIEW).count()
    approved_count = requests_qs.filter(status=CertificateRequest.STATUS_APPROVED).count()
    rejected_count = requests_qs.filter(status=CertificateRequest.STATUS_REJECTED).count()
    generated_count = requests_qs.filter(status=CertificateRequest.STATUS_GENERATED).count()

    # Document verification
    total_docs = docs_qs.count()
    doc_pending = docs_qs.filter(verification_status=StudentDocument.STATUS_PENDING).count()
    doc_verified = docs_qs.filter(verification_status=StudentDocument.STATUS_VERIFIED).count()
    doc_rejected = docs_qs.filter(verification_status=StudentDocument.STATUS_REJECTED).count()

    # Certificate type breakdown
    type_breakdown = requests_qs.values("certificate_type__name").annotate(
        count=Count("id")
    ).order_by("-count")

    return {
        "total_requests": total_requests,
        "pending_count": pending_count,
        "under_review_count": under_review_count,
        "approved_count": approved_count,
        "rejected_count": rejected_count,
        "generated_count": generated_count,
        "total_documents": total_docs,
        "doc_pending": doc_pending,
        "doc_verified": doc_verified,
        "doc_rejected": doc_rejected,
        "type_breakdown": type_breakdown,
    }


# ==============================================================================
# STUDENT PERSONAL ANALYTICS (ONLY SELF-DATA)
# ==============================================================================

def get_student_personal_analytics(student):
    """
    Aggregates personal academic, attendance, fee, library, and certificate records
    strictly for the logged-in student.
    """
    # 1. Attendance Summary
    att_qs = Attendance.objects.filter(student=student).select_related("subject")
    total_classes = att_qs.count()
    present_classes = att_qs.filter(present=True).count()
    absent_classes = total_classes - present_classes
    attendance_pct = round((present_classes / total_classes) * 100, 1) if total_classes > 0 else 0.0

    subject_att_list = []
    subjects_ids = att_qs.values_list("subject_id", flat=True).distinct()
    for s_id in subjects_ids:
        subj = Subject.objects.get(id=s_id)
        s_att = att_qs.filter(subject_id=s_id)
        s_tot = s_att.count()
        s_pres = s_att.filter(present=True).count()
        s_pct = round((s_pres / s_tot) * 100, 1) if s_tot > 0 else 0.0
        subject_att_list.append({
            "subject": subj.name,
            "code": subj.code,
            "total": s_tot,
            "present": s_pres,
            "percentage": s_pct,
        })

    # 2. Academic Marks
    marks_records = Marks.objects.filter(student=student).select_related("subject")
    exam_marks_records = StudentExamMark.objects.filter(student=student).select_related("exam", "subject")

    overall_marks_pct = None
    if exam_marks_records.exists():
        avg_val = exam_marks_records.aggregate(avg=Avg("percentage"))["avg"]
        if avg_val is not None:
            overall_marks_pct = round(float(avg_val), 1)
    elif marks_records.exists():
        avg_val = marks_records.aggregate(
            avg_gt=Avg(F("cat_1") + F("cat_2") + F("cat_3") + F("cat_1_assignment") + F("cat_2_assignment") + F("cat_3_assignment"))
        )["avg_gt"]
        if avg_val is not None:
            overall_marks_pct = round((float(avg_val) / 150.0) * 100, 1)

    # 3. Fees Summary
    fee_records = FeeRecord.objects.filter(student=student)
    total_fees = fee_records.aggregate(s=Sum("amount"))["s"] or Decimal("0.00")
    paid_fees = FeePayment.objects.filter(fee_record__in=fee_records).aggregate(s=Sum("amount"))["s"] or Decimal("0.00")
    balance_fees = max(total_fees - paid_fees, Decimal("0.00"))

    # 4. Library Summary
    loans = BookLoan.objects.filter(student=student).select_related("book")
    active_loans = loans.filter(return_date__isnull=True)
    today = timezone.localdate()
    overdue_count = active_loans.filter(due_date__lt=today).count()
    total_fines = loans.aggregate(s=Sum("fine_amount"))["s"] or Decimal("0.00")

    # 5. Certificates
    cert_requests = CertificateRequest.objects.filter(student=student).select_related("certificate_type")

    # 6. Placement
    placement_profile = StudentPlacementProfile.objects.filter(student=student).first()
    placement_apps = PlacementApplication.objects.filter(student=student).select_related(
        "placement_drive", "placement_drive__company"
    )

    # 7. Assignments
    assignments = []
    if student.course:
        course_assignments = Assignment.objects.filter(
            course=student.course, year=student.year, is_active=True
        ).select_related("subject", "faculty")
        submissions = {sub.assignment_id: sub for sub in AssignmentSubmission.objects.filter(student=student)}

        for a in course_assignments:
            sub = submissions.get(a.id)
            assignments.append({
                "assignment": a,
                "submission": sub,
                "is_submitted": bool(sub),
                "status": sub.status if sub else ("Deadline Passed" if a.is_deadline_passed else "Pending Submission"),
                "marks_obtained": sub.marks_obtained if sub else None,
            })

    return {
        "student": student,
        "attendance": {
            "total_classes": total_classes,
            "present_classes": present_classes,
            "absent_classes": absent_classes,
            "percentage": attendance_pct,
            "subjects": subject_att_list,
        },
        "marks": {
            "overall_percentage": overall_marks_pct,
            "internal_records": marks_records,
            "exam_records": exam_marks_records,
        },
        "fees": {
            "total": total_fees,
            "paid": paid_fees,
            "balance": balance_fees,
            "records": fee_records,
        },
        "library": {
            "active_loans": active_loans,
            "overdue_count": overdue_count,
            "total_fines": total_fines,
        },
        "certificates": {
            "requests": cert_requests,
        },
        "placements": {
            "profile": placement_profile,
            "applications": placement_apps,
        },
        "assignments": assignments,
    }
