from django.core.management.base import BaseCommand

from students.models import Department, Course


# ================================================================
# TAKSHASHILA UNIVERSITY — SCHOOLS & COURSES
#
# The three B.Tech programmes under "School of Core Engineering"
# (Mechanical, Civil, Electrical) are not spelled out with exact
# titles in the source list — the source just says the school
# "describes disciplines including Mechanical, Civil and
# Electrical engineering". Added here with standard names; rename
# in /admin/ if the official titles differ.
# ================================================================

SCHOOLS = {

    "School of Computational Engineering": [
        "B.Tech Computer Science and Engineering",
        "B.Tech Artificial Intelligence and Data Science",
        "B.Tech CSE (Artificial Intelligence & Machine Learning)",
        "B.Tech Information Technology",
        "B.Tech CSE (Cyber Security)",
        "B.Tech CSE (Internet of Things)",
        "B.Tech Computer Science & Business Systems",
        "B.Tech Computer & Communication Engineering",
        "B.Tech CSE (Blockchain)",
        "B.Tech CSE – Software Product Engineering",
        "M.Tech Computer Science & Engineering",
        "M.Tech CSE (Artificial Intelligence)",
        "M.Tech CSE – Big Data",
    ],

    "School of Core Engineering": [
        "B.Tech Electronics & Communication Engineering",
        "B.Tech Mechanical Engineering",
        "B.Tech Civil Engineering",
        "B.Tech Electrical Engineering",
    ],

    "School of Computer Science": [
        "B.Sc Computer Science",
        "B.Sc Computer Science (AI & Data Science)",
        "B.Sc Computer Science (AI & Machine Learning)",
        "BCA – Bachelor of Computer Applications",
        "BCA (Full Stack Development)",
        "BCA (AI & Machine Learning)",
        "M.Sc Computer Science",
        "M.Sc Computer Science (AI & Data Science)",
        "MCA – Master of Computer Applications",
        "MCA (Data Science with TRANSORG)",
    ],

    "School of Basic Sciences": [
        "B.Sc Mathematics",
        "B.Sc Physics",
        "B.Sc Chemistry",
        "M.Sc Mathematics",
        "M.Sc Physics",
        "M.Sc Chemistry",
        "Ph.D Mathematics",
        "Ph.D Physics",
        "Ph.D Chemistry",
    ],

    "School of Agricultural Sciences": [
        "B.Sc. (Hons.) Agriculture",
        "M.Sc Agronomy",
        "M.Sc Soil Science",
        "M.Sc Agricultural Economics",
        "M.Sc Plant Pathology",
        "M.Sc Entomology",
    ],

    "School of Commerce": [
        "B.Com General",
        "B.Com Accounting & Finance",
        "B.Com Computer Application",
        "B.Com Professional Accounting",
        "B.Com Corporate Secretaryship",
        "B.Com FinTech with AI",
        "B.Com CMA",
        "M.Com",
        "Ph.D Commerce",
    ],

    "School of Management Studies": [
        "BBA",
        "BBA (FinTech & Digital Banking)",
        "BBA (Business Analytics)",
        "MBA",
    ],

    "School of Humanities": [
        "B.A Tamil",
        "B.A English",
        "M.A Tamil",
        "M.A English",
        "Ph.D Tamil",
        "Ph.D English",
    ],

    "School of Social Sciences": [
        "B.A Economics",
        "B.A Defence & Strategic Studies",
        "B.A International Relations & Public Policy",
        "B.A Psychology",
        "M.A Economics",
        "M.A Psychology",
        "MSW – Master of Social Work",
        "Ph.D Economics",
    ],

    "School of Allied Health Sciences": [
        "B.Sc Radiography & Imaging Technology",
        "B.Sc Cardiac Technology",
        "B.Sc Medical Lab Technology",
        "B.Sc Physician Assistant",
        "B.Sc Optometry",
        "B.Sc Operation Theatre & Anaesthesia Technology",
        "B.Sc Cardiac Perfusion Technology",
        "B.Sc Clinical Embryology",
    ],

    "School of Physiotherapy": [
        "BPT – Bachelor of Physiotherapy",
    ],

    "School of Pharmacy": [
        "B.Pharm – Bachelor of Pharmacy",
    ],

    "School of Nursing": [
        "B.Sc Nursing",
    ],

    "Takshashila Medical College": [
        "MBBS – Bachelor of Medicine and Bachelor of Surgery",
    ],

}


class Command(BaseCommand):

    help = (
        "Seeds all Takshashila University Schools and their "
        "Courses. Safe to run more than once — existing Schools "
        "and Courses are reused, not duplicated."
    )

    def handle(self, *args, **options):

        # ============================================================
        # Fold the existing generic "Computer Science" department
        # (used by your current demo data — Ramesh A, kumar, Arun
        # Kumar, subject "python programming") into the real
        # "School of Computer Science", instead of creating a
        # duplicate school.
        # ============================================================

        legacy = Department.objects.filter(
            name="Computer Science"
        ).first()

        if legacy is not None:
            legacy.name = "School of Computer Science"
            legacy.save()
            self.stdout.write(
                "Renamed existing 'Computer Science' department "
                "to 'School of Computer Science'."
            )

        schools_created = 0
        courses_created = 0

        for school_name, course_names in SCHOOLS.items():

            department, created = Department.objects.get_or_create(
                name=school_name
            )

            if created:
                schools_created += 1

            for course_name in course_names:

                course, created = Course.objects.get_or_create(
                    name=course_name,
                    department=department,
                )

                if created:
                    courses_created += 1

        self.stdout.write(
            f"Done. {schools_created} new school(s), "
            f"{courses_created} new course(s) added."
        )
