"""
School -> Degree (Course) -> Class (Year) scoping for the admin
dashboard, plus the aggregate numbers shown at each level.

Filters arrive as ?school=<id>&course=<id>&year=<n>.
"""

from django.db.models import Count, Avg, F, Q

from students.models import Department, Course, Student
from faculty.models import Faculty, Subject
from attendance.models import Attendance
from marks.models import Marks
from timetable.models import Timetable, SchoolClass, Period, DAY_CHOICES

MAX_MARKS = 120  # 3 CATs x 40


def pct(part, total):
    if not total:
        return None
    return round(part * 100 / total, 1)


def _int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


# ----------------------------------------------------------------
# Parse + validate the three filters
# ----------------------------------------------------------------

def parse_scope(params):

    school = None
    course = None
    year = None

    school_id = _int(params.get("school"))
    course_id = _int(params.get("course"))
    year_val = _int(params.get("year"))

    if school_id:
        school = Department.objects.filter(id=school_id).first()

    if course_id:
        course = Course.objects.select_related("department").filter(id=course_id).first()

        if course is not None:
            if school is not None and course.department_id != school.id:
                course = None      # degree doesn't belong to that school
            elif school is None:
                school = course.department

    if course is not None and year_val:
        year = year_val

    if school is None:
        level = "all"
    elif course is None:
        level = "school"
    elif year is None:
        level = "course"
    else:
        level = "class"

    return {
        "school": school,
        "course": course,
        "year": year,
        "level": level,
    }


def scoped_students(scope, approved=True):

    qs = Student.objects.select_related("department", "course")

    if approved is not None:
        qs = qs.filter(is_approved=approved)

    if scope["school"]:
        qs = qs.filter(department=scope["school"])

    if scope["course"]:
        qs = qs.filter(course=scope["course"])

    if scope["year"]:
        qs = qs.filter(year=scope["year"])

    return qs


def scoped_faculty(scope, approved=True):

    qs = Faculty.objects.select_related("department")

    if approved is not None:
        qs = qs.filter(is_approved=approved)

    if scope["school"]:
        qs = qs.filter(department=scope["school"])

    if scope["course"]:

        slots = Timetable.objects.filter(school_class__course=scope["course"])

        if scope["year"]:
            slots = slots.filter(school_class__year=scope["year"])

        qs = qs.filter(id__in=slots.values("faculty_id"))

    return qs


# ----------------------------------------------------------------
# Aggregates
# ----------------------------------------------------------------

def overall_stats(students_qs):

    att = Attendance.objects.filter(student__in=students_qs).aggregate(
        total=Count("id"),
        present=Count("id", filter=Q(present=True)),
    )

    marks = Marks.objects.filter(student__in=students_qs).aggregate(
        avg=Avg(F("cat_1") + F("cat_2") + F("cat_3")),
    )

    return {
        "attendance_pct": pct(att["present"], att["total"]),
        "attendance_records": att["total"],
        "marks_pct": (
            round(marks["avg"] * 100 / MAX_MARKS, 1)
            if marks["avg"] is not None else None
        ),
    }


def grouped_stats(students_qs, key):
    """
    Attendance % and average marks % grouped by a student field
    (e.g. 'student__department_id'). Returns {key_value: {...}}.
    """

    out = {}

    for row in (
        Attendance.objects.filter(student__in=students_qs)
        .values(key)
        .annotate(total=Count("id"), present=Count("id", filter=Q(present=True)))
    ):
        out.setdefault(row[key], {})["attendance_pct"] = pct(row["present"], row["total"])

    for row in (
        Marks.objects.filter(student__in=students_qs)
        .values(key)
        .annotate(avg=Avg(F("cat_1") + F("cat_2") + F("cat_3")))
    ):
        out.setdefault(row[key], {})["marks_pct"] = (
            round(row["avg"] * 100 / MAX_MARKS, 1) if row["avg"] is not None else None
        )

    return out


def per_student_stats(student_ids):
    """Attendance % and marks % for a small list of students (one page)."""

    stats = {sid: {"attendance_pct": None, "marks_pct": None} for sid in student_ids}

    for row in (
        Attendance.objects.filter(student_id__in=student_ids)
        .values("student_id")
        .annotate(total=Count("id"), present=Count("id", filter=Q(present=True)))
    ):
        stats[row["student_id"]]["attendance_pct"] = pct(row["present"], row["total"])

    for row in (
        Marks.objects.filter(student_id__in=student_ids)
        .values("student_id")
        .annotate(avg=Avg(F("cat_1") + F("cat_2") + F("cat_3")))
    ):
        stats[row["student_id"]]["marks_pct"] = (
            round(row["avg"] * 100 / MAX_MARKS, 1) if row["avg"] is not None else None
        )

    return stats


# ----------------------------------------------------------------
# Data for the dependent dropdowns (School -> Degree -> Class)
# ----------------------------------------------------------------

def filter_tree():
    """
    [{id, name, courses: [{id, name, years: [1, 2, ...]}]}]
    A class year is listed if a SchoolClass exists for it OR any
    student is enrolled in it.
    """

    years = {}

    for course_id, year in Student.objects.filter(
        course__isnull=False
    ).values_list("course_id", "year").distinct():
        years.setdefault(course_id, set()).add(year)

    for course_id, year in SchoolClass.objects.values_list("course_id", "year"):
        years.setdefault(course_id, set()).add(year)

    tree = []

    for dept in Department.objects.order_by("name").prefetch_related("courses"):
        tree.append({
            "id": dept.id,
            "name": dept.name,
            "courses": [
                {
                    "id": c.id,
                    "name": c.name,
                    "years": sorted(years.get(c.id, [])),
                }
                for c in sorted(dept.courses.all(), key=lambda c: c.name)
            ],
        })

    return tree


# ----------------------------------------------------------------
# Class timetable grid (Mon-Sat x periods)
# ----------------------------------------------------------------

def class_timetable(course, year):

    school_class = SchoolClass.objects.filter(course=course, year=year).first()

    if school_class is None:
        return None

    slots = Timetable.objects.filter(
        school_class=school_class
    ).select_related("period", "subject", "faculty")

    grid = {(s.period_id, s.day_of_week): s for s in slots}

    rows = []

    for period in Period.objects.all():
        rows.append({
            "period": period,
            "cells": [grid.get((period.id, code)) for code, _ in DAY_CHOICES],
        })

    return {
        "days": [label for _, label in DAY_CHOICES],
        "rows": rows,
        "has_slots": bool(grid),
    }
