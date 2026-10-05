from decimal import Decimal
from django.utils import timezone
from django.db.models import Avg

from marks.models import Marks
from exams.models import StudentExamMark


def get_student_academic_summary(student):
    """
    Computes a student's aggregate academic percentage and standing backlogs
    using live academic records across exams and internal marks.
    """
    if not student:
        return {"percentage": Decimal("0.0"), "backlogs": 0}

    # 1. Check StudentExamMark records
    exam_marks = StudentExamMark.objects.filter(student=student)
    if exam_marks.exists():
        total_obt = sum(m.marks_obtained for m in exam_marks)
        total_max = sum(m.max_marks for m in exam_marks)
        pct = (Decimal(total_obt) / Decimal(total_max) * 100) if total_max > 0 else Decimal("0.0")
        backlogs = exam_marks.filter(result_status="Fail").count()
        return {
            "percentage": round(pct, 2),
            "backlogs": backlogs,
        }

    # 2. Check internal Marks records (grand_total max is 150)
    internal_marks = Marks.objects.filter(student=student)
    if internal_marks.exists():
        total_pct = sum((Decimal(m.grand_total) / Decimal("150.0") * 100) for m in internal_marks)
        avg_pct = total_pct / Decimal(internal_marks.count())
        backlogs = sum(1 for m in internal_marks if (Decimal(m.grand_total) / Decimal("1.5")) < 40)
        return {
            "percentage": round(avg_pct, 2),
            "backlogs": backlogs,
        }

    # 3. Check placement profile if set
    from placements.models import StudentPlacementProfile
    profile = StudentPlacementProfile.objects.filter(student=student).first()
    if profile and profile.cgpa_or_percentage is not None:
        return {
            "percentage": profile.cgpa_or_percentage,
            "backlogs": profile.active_backlogs,
        }

    return {"percentage": Decimal("75.0"), "backlogs": 0}


def check_student_eligibility(student, drive):
    """
    Comprehensive, reusable eligibility evaluation engine.
    Returns:
        (is_eligible: bool, reasons: list[str])
    """
    if not student:
        return False, ["Student record could not be found."]

    reasons = []

    # 1. Student active status
    if not student.is_active:
        reasons.append("Your student account is currently marked as inactive.")

    # 2. School / Department eligibility
    if drive.eligible_departments.exists():
        if student.department not in drive.eligible_departments.all():
            allowed_depts = ", ".join(d.name for d in drive.eligible_departments.all())
            reasons.append(
                f"Your school/department ({student.department.name}) is not eligible. Eligible schools: {allowed_depts}."
            )

    # 3. Course / Degree eligibility
    if drive.eligible_courses.exists():
        if not student.course or (student.course not in drive.eligible_courses.all()):
            student_course_name = student.course.name if student.course else "No Degree Assigned"
            allowed_courses = ", ".join(c.name for c in drive.eligible_courses.all())
            reasons.append(
                f"Your degree ({student_course_name}) is not eligible. Eligible courses: {allowed_courses}."
            )

    # 4. Graduating year eligibility
    if drive.eligible_year != 0 and student.year != drive.eligible_year:
        reasons.append(
            f"This placement drive is open only for Year {drive.eligible_year} students (you are currently in Year {student.year})."
        )

    # 5. Academic Percentage & Backlogs
    academic = get_student_academic_summary(student)
    student_pct = academic["percentage"]
    student_backlogs = academic["backlogs"]

    if student_pct < drive.minimum_percentage:
        reasons.append(
            f"Not eligible because your aggregate percentage ({student_pct:.1f}%) is below the required {drive.minimum_percentage}%."
        )

    if student_backlogs > drive.maximum_backlogs:
        reasons.append(
            f"Not eligible because you have {student_backlogs} standing backlog(s), which exceeds the maximum allowed ({drive.maximum_backlogs})."
        )

    # 6. Drive status & application deadline
    today = timezone.localdate()
    if drive.status != "Open":
        reasons.append(f"This placement drive is currently {drive.status}.")
    elif drive.application_deadline < today:
        reasons.append(
            f"The application deadline for this drive expired on {drive.application_deadline.strftime('%d %b %Y')} (the deadline has passed)."
        )

    if not reasons:
        return True, ["Eligible"]
    return False, reasons
