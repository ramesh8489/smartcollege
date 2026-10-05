from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse

from students.models import Student, Department, Course
from faculty.models import Faculty, Subject
from attendance.models import Attendance
from marks.models import Marks
from fees.models import FeeRecord, FeePayment
from library.models import Book, BookLoan
from timetable.models import SchoolIncharge, SchoolClass, Period, Timetable
from analytics.models import AnalyticsSetting
from analytics import services


class AnalyticsTestSuite(TestCase):
    """
    Comprehensive tests for AI & Advanced Analytics Dashboard.
    Validates:
    - Admin access, calculations, charts, filters
    - School Incharge school-level scoping
    - Faculty subject-level scoping
    - Student personal data isolation & URL manipulation defense (403)
    - Excel & PDF exports
    - Threshold configuration
    - Zero data / empty state safety
    """

    def setUp(self):
        self.client = Client()

        # 1. Departments & Courses
        self.dept_cs = Department.objects.create(name="School of Computer Science")
        self.dept_eng = Department.objects.create(name="School of Engineering")

        self.course_msc = Course.objects.create(name="M.Sc Computer Science", department=self.dept_cs)
        self.course_btech = Course.objects.create(name="B.Tech CS", department=self.dept_eng)

        # 2. Users
        self.admin_user = User.objects.create_superuser(username="test_admin", password="password123")

        self.incharge_user = User.objects.create_user(username="test_incharge", password="password123")
        self.faculty_user = User.objects.create_user(username="test_faculty", password="password123")

        self.student1_user = User.objects.create_user(username="test_student1", password="password123")
        self.student2_user = User.objects.create_user(username="test_student2", password="password123")

        # 3. Faculty profiles
        self.incharge_fac = Faculty.objects.create(
            user=self.incharge_user, name="Prof Incharge", faculty_id="FAC_INC_01",
            email="incharge@test.com", department=self.dept_cs
        )
        self.school_incharge = SchoolIncharge.objects.create(
            department=self.dept_cs, faculty=self.incharge_fac
        )

        self.reg_fac = Faculty.objects.create(
            user=self.faculty_user, name="Prof Regular", faculty_id="FAC_REG_01",
            email="faculty@test.com", department=self.dept_cs
        )

        # 4. Subjects
        self.subj_python = Subject.objects.create(
            name="Python Programming", code="CS101", department=self.dept_cs,
            faculty=self.reg_fac, course=self.course_msc, year=1
        )
        self.subj_ai = Subject.objects.create(
            name="Artificial Intelligence", code="CS102", department=self.dept_cs,
            faculty=self.incharge_fac, course=self.course_msc, year=1
        )

        # 5. Students
        self.student1 = Student.objects.create(
            user=self.student1_user, name="Alice", roll_no="CS001",
            email="alice@test.com", department=self.dept_cs, course=self.course_msc, year=1
        )
        self.student2 = Student.objects.create(
            user=self.student2_user, name="Bob", roll_no="CS002",
            email="bob@test.com", department=self.dept_cs, course=self.course_msc, year=1
        )

        # 6. Attendance records
        # Alice: 1 Present, 1 Absent (50% -> Critical < 65%)
        Attendance.objects.create(student=self.student1, subject=self.subj_python, date="2026-10-01", present=True)
        Attendance.objects.create(student=self.student1, subject=self.subj_python, date="2026-10-02", present=False)
        # Bob: 2 Present (100% -> Safe)
        Attendance.objects.create(student=self.student2, subject=self.subj_python, date="2026-10-01", present=True)
        Attendance.objects.create(student=self.student2, subject=self.subj_python, date="2026-10-02", present=True)

        # 7. Marks records
        # Alice: CAT 1=15, 2=15, 3=15 (Total=45 / 150 = 30% -> Low / Fail)
        Marks.objects.create(student=self.student1, subject=self.subj_python, cat_1=15, cat_2=15, cat_3=15)
        # Bob: CAT 1=35, 2=35, 3=35 (Total=105 / 150 = 70% -> Distinction)
        Marks.objects.create(student=self.student2, subject=self.subj_python, cat_1=35, cat_2=35, cat_3=35)

        # 8. Fees
        # Alice has 10,000 total, 0 paid -> 10,000 balance
        FeeRecord.objects.create(student=self.student1, fee_type="TUITION", title="Semester 1 Tuition", amount=10000.00, status="PENDING")

        # 9. Settings
        self.settings = AnalyticsSetting.get_settings()
        self.settings.attendance_warning_threshold = 75.0
        self.settings.attendance_critical_threshold = 65.0
        self.settings.marks_passing_threshold = 40.0
        self.settings.save()

    def test_admin_dashboard_access(self):
        """Admin should access overall analytics with valid statistics, charts and insights."""
        self.client.login(username="test_admin", password="password123")
        response = self.client.get("/analytics/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "AI & Advanced Analytics Dashboard")
        self.assertContains(response, "Total Students")
        self.assertContains(response, "Alice")
        self.assertContains(response, "Python Programming")

        # Verify KPI summary values in context
        kpi = response.context["kpi"]
        self.assertEqual(kpi["total_students"], 2)
        self.assertEqual(kpi["total_faculty"], 2)
        # Overall attendance: 3 present out of 4 = 75.0%
        self.assertEqual(kpi["avg_attendance"], 75.0)

    def test_academic_analytics_view(self):
        """Academic analytics should show subject performance and top/lowest performers."""
        self.client.login(username="test_admin", password="password123")
        response = self.client.get("/analytics/academic/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Subject-wise Performance Diagnostics")
        academic = response.context["academic"]
        self.assertTrue(len(academic["subjects"]) > 0)
        self.assertEqual(academic["subjects"][0]["name"], "Python Programming")

    def test_attendance_analytics_view(self):
        """Attendance analytics should categorize shortage students accurately."""
        self.client.login(username="test_admin", password="password123")
        response = self.client.get("/analytics/attendance/")
        self.assertEqual(response.status_code, 200)
        att = response.context["attendance"]
        # Alice is critical (<65%), Bob is safe (>=75%)
        self.assertEqual(att["critical_count"], 1)
        self.assertEqual(att["safe_count"], 1)
        self.assertContains(response, "Attendance Risk & Compliance Roster")

    def test_at_risk_student_identification(self):
        """At-risk student calculation should flag Alice for low attendance, low marks, and fee balance."""
        self.client.login(username="test_admin", password="password123")
        response = self.client.get("/analytics/risk/")
        self.assertEqual(response.status_code, 200)
        risk = response.context["risk"]
        self.assertEqual(risk["high_risk_count"], 1)

        alice_risk = next(s for s in risk["students"] if s["student"].id == self.student1.id)
        self.assertEqual(alice_risk["risk_level"], "High")
        self.assertTrue(any("Attendance critical" in r for r in alice_risk["reasons"]))
        self.assertTrue(any("Academic score critical" in r for r in alice_risk["reasons"]))
        self.assertTrue(any("Outstanding fee balance" in r for r in alice_risk["reasons"]))

    def test_school_incharge_scoping(self):
        """School Incharge must only see data for their assigned School."""
        self.client.login(username="test_incharge", password="password123")
        response = self.client.get("/analytics/")
        self.assertEqual(response.status_code, 200)
        scope = response.context["scope"]
        self.assertEqual(scope["role"], "school_incharge")
        self.assertEqual(scope["school"].id, self.dept_cs.id)

        # If incharge attempts to filter to Engineering school:
        resp_manip = self.client.get(f"/analytics/?school={self.dept_eng.id}")
        self.assertEqual(resp_manip.status_code, 200)
        # Must still be locked to dept_cs!
        self.assertEqual(resp_manip.context["scope"]["school"].id, self.dept_cs.id)

    def test_faculty_view(self):
        """Faculty member can access faculty workload view."""
        self.client.login(username="test_faculty", password="password123")
        response = self.client.get("/analytics/faculty/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Teaching Workload & Student Engagement Diagnostics")

    def test_student_auto_redirect_and_personal_analytics(self):
        """Student accessing /analytics/ should be redirected to /analytics/my/ and see only their records."""
        self.client.login(username="test_student1", password="password123")
        response = self.client.get("/analytics/")
        self.assertRedirects(response, "/analytics/my/")

        resp_my = self.client.get("/analytics/my/")
        self.assertEqual(resp_my.status_code, 200)
        self.assertContains(resp_my, "Alice")
        self.assertContains(resp_my, "CS001")
        # Alice should NOT see Bob's data
        self.assertNotContains(resp_my, "CS002")

    def test_security_prevent_student_url_manipulation(self):
        """A student must NOT be allowed to access another student's analytics via URL manipulation."""
        self.client.login(username="test_student1", password="password123")

        # Student 1 attempts to access Student 2's direct URL
        response = self.client.get(f"/analytics/student/{self.student2.id}/")
        self.assertEqual(response.status_code, 403)

        # Student 1 attempts to pass ?student_id= query param
        response_param = self.client.get(f"/analytics/my/?student_id={self.student2.id}")
        self.assertEqual(response_param.status_code, 403)

    def test_security_prevent_student_export(self):
        """Students should not be allowed to export institutional reports."""
        self.client.login(username="test_student1", password="password123")
        response = self.client.get("/analytics/export/excel/")
        self.assertEqual(response.status_code, 403)

        response_pdf = self.client.get("/analytics/export/pdf/")
        self.assertEqual(response_pdf.status_code, 403)

    def test_admin_excel_export(self):
        """Admin can export analytics to Excel."""
        self.client.login(username="test_admin", password="password123")
        response = self.client.get("/analytics/export/excel/?type=overall")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        self.assertTrue(len(response.content) > 1000)

    def test_admin_pdf_export(self):
        """Admin can export analytics report to PDF."""
        self.client.login(username="test_admin", password="password123")
        response = self.client.get("/analytics/export/pdf/?type=overall")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertTrue(len(response.content) > 1000)

    def test_fees_analytics_view(self):
        """Fees analytics should compute total, collected, and outstanding balances."""
        self.client.login(username="test_admin", password="password123")
        response = self.client.get("/analytics/fees/")
        self.assertEqual(response.status_code, 200)
        fees = response.context["fees"]
        self.assertEqual(fees["total_fees"], 10000.00)
        self.assertEqual(fees["total_outstanding"], 10000.00)

    def test_library_analytics_view(self):
        """Library analytics handles catalog and circulation without error."""
        self.client.login(username="test_admin", password="password123")
        response = self.client.get("/analytics/library/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Library Catalog & Circulation Analytics")

    def test_placements_and_certificates_views(self):
        """Placements and certificates views render properly even with zero or partial records."""
        self.client.login(username="test_admin", password="password123")
        resp_p = self.client.get("/analytics/placements/")
        self.assertEqual(resp_p.status_code, 200)

        resp_c = self.client.get("/analytics/certificates/")
        self.assertEqual(resp_c.status_code, 200)
