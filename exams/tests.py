import datetime
from decimal import Decimal
from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse
from django.core.exceptions import ValidationError

from exams.models import Exam, ExamSchedule, StudentExamMark, compute_grade_and_points
from exams.forms import ExamForm, ExamScheduleForm, StudentExamMarkForm
from students.models import Course, Department, Student
from faculty.models import Subject, Faculty


class ExamManagementTestCase(TestCase):
    def setUp(self):
        self.client = Client()

        # Admin user
        self.admin_user = User.objects.create_superuser(
            username="admin_test",
            email="admin_test@smartcollege.com",
            password="adminpassword123"
        )

        # Department & Course
        self.dept = Department.objects.create(name="School of Computing")
        self.course = Course.objects.create(name="Master of Computer Applications", department=self.dept)

        # Faculty 1 (Assigned to subject 1)
        self.faculty_user = User.objects.create_user(
            username="faculty_test",
            email="faculty_test@smartcollege.com",
            password="facultypassword123"
        )
        self.faculty = Faculty.objects.create(
            user=self.faculty_user,
            name="Dr. Alan Turing",
            faculty_id="FAC999",
            email="faculty_test@smartcollege.com",
            department=self.dept
        )

        # Faculty 2 (Not assigned to subject 1)
        self.faculty_user2 = User.objects.create_user(
            username="faculty_test2",
            email="faculty_test2@smartcollege.com",
            password="facultypassword123"
        )
        self.faculty2 = Faculty.objects.create(
            user=self.faculty_user2,
            name="Dr. Grace Hopper",
            faculty_id="FAC888",
            email="faculty_test2@smartcollege.com",
            department=self.dept
        )

        # Students
        self.student_user = User.objects.create_user(
            username="student_test",
            email="student_test@smartcollege.com",
            password="studentpassword123"
        )
        self.student = Student.objects.create(
            user=self.student_user,
            name="Ada Lovelace",
            roll_no="MCA202601",
            sif_number="SIF9999",
            course=self.course,
            department=self.dept,
            year=2,
            is_approved=True
        )

        self.student2_user = User.objects.create_user(
            username="student_test2",
            email="student_test2@smartcollege.com",
            password="studentpassword123"
        )
        self.student2 = Student.objects.create(
            user=self.student2_user,
            name="Charles Babbage",
            roll_no="MCA202602",
            sif_number="SIF9998",
            course=self.course,
            department=self.dept,
            year=2,
            is_approved=True
        )

        # Subjects
        self.subject = Subject.objects.create(
            name="Advanced Database Systems",
            code="MCA301",
            department=self.dept,
            faculty=self.faculty,
            course=self.course,
            year=2,
            semester=3,
            credits=4.0
        )
        self.subject2 = Subject.objects.create(
            name="Distributed Systems",
            code="MCA302",
            department=self.dept,
            faculty=self.faculty,
            course=self.course,
            year=2,
            semester=3,
            credits=4.0
        )

        # Primary Exam Record
        self.exam = Exam.objects.create(
            name="CAT 1 Examination - Oct 2026",
            exam_type="CAT 1",
            academic_year="2026-2027",
            semester=3,
            course=self.course,
            year=2,
            start_date=datetime.date(2026, 10, 10),
            end_date=datetime.date(2026, 10, 20),
            description="Continuous assessment test covering units 1 and 2.",
            is_active=True,
            created_by=self.admin_user
        )

        # Exam Schedules with room_number and status
        self.schedule = ExamSchedule.objects.create(
            exam=self.exam,
            subject=self.subject,
            exam_date=datetime.date(2026, 10, 15),
            start_time=datetime.time(10, 0),
            end_time=datetime.time(11, 30),
            room_number="Exam Hall A",
            room="Exam Hall A",
            invigilator=self.faculty,
            max_marks=50,
            status="Scheduled"
        )

    def test_exam_fields_and_string_representation(self):
        """Verify all requested exam fields exist and string representation works."""
        self.assertEqual(self.exam.name, "CAT 1 Examination - Oct 2026")
        self.assertEqual(self.exam.exam_type, "CAT 1")
        self.assertEqual(self.exam.academic_year, "2026-2027")
        self.assertEqual(self.exam.semester, 3)
        self.assertEqual(self.exam.course, self.course)
        self.assertEqual(self.exam.year, 2)
        self.assertEqual(self.exam.start_date, datetime.date(2026, 10, 10))
        self.assertEqual(self.exam.end_date, datetime.date(2026, 10, 20))
        self.assertEqual(self.exam.description, "Continuous assessment test covering units 1 and 2.")
        self.assertTrue(self.exam.is_active)
        self.assertIn("CAT 1 Examination - Oct 2026", str(self.exam))

    def test_all_requested_exam_types(self):
        """Verify all 7 requested exam types can be created."""
        exam_types = [
            "CAT 1",
            "CAT 2",
            "CAT 3",
            "Model Exam",
            "Semester Exam",
            "Internal Exam",
            "Practical Exam",
        ]
        for et in exam_types:
            exam = Exam.objects.create(
                name=f"{et} Test Session",
                exam_type=et,
                academic_year="2026-2027",
                semester=1,
                course=self.course,
                year=1,
                start_date=datetime.date(2026, 12, 1),
                end_date=datetime.date(2026, 12, 10),
                is_active=True
            )
            self.assertEqual(exam.exam_type, et)

    def test_exam_schedule_fields(self):
        """Verify ExamSchedule fields: room_number, max_marks, status."""
        self.assertEqual(self.schedule.room_number, "Exam Hall A")
        self.assertEqual(self.schedule.max_marks, 50)
        self.assertEqual(self.schedule.status, "Scheduled")

    def test_student_exam_mark_automatic_calculation(self):
        """Test automatic calculation of Percentage, Grade, Grade Point, and Pass/Fail status."""
        mark = StudentExamMark.objects.create(
            student=self.student,
            exam=self.exam,
            subject=self.subject,
            max_marks=50,
            marks_obtained=Decimal("45.00"),
            entered_by=self.admin_user
        )
        # 45 / 50 = 90% -> Grade O, GP 10.0, Pass
        self.assertEqual(mark.percentage, Decimal("90.00"))
        self.assertEqual(mark.grade, "O")
        self.assertEqual(mark.grade_point, Decimal("10.00"))
        self.assertEqual(mark.result_status, "Pass")

    def test_student_exam_mark_fail_and_absent(self):
        """Test failure grading (< 40%) and absent handling."""
        fail_mark = StudentExamMark.objects.create(
            student=self.student2,
            exam=self.exam,
            subject=self.subject,
            max_marks=50,
            marks_obtained=Decimal("15.00"),
            entered_by=self.admin_user
        )
        # 15 / 50 = 30% -> Grade F, GP 0.0, Fail
        self.assertEqual(fail_mark.percentage, Decimal("30.00"))
        self.assertEqual(fail_mark.grade, "F")
        self.assertEqual(fail_mark.result_status, "Fail")

        absent_mark = StudentExamMark.objects.create(
            student=self.student,
            exam=self.exam,
            subject=self.subject2,
            max_marks=50,
            marks_obtained=Decimal("0.00"),
            result_status="Absent",
            entered_by=self.admin_user
        )
        self.assertEqual(absent_mark.grade, "AB")
        self.assertEqual(absent_mark.percentage, Decimal("0.00"))

    def test_validation_marks_greater_than_max(self):
        """Ensure validation rejects marks_obtained > max_marks."""
        mark = StudentExamMark(
            student=self.student,
            exam=self.exam,
            subject=self.subject,
            max_marks=50,
            marks_obtained=Decimal("55.00")
        )
        with self.assertRaises(ValidationError):
            mark.clean()

        with self.assertRaises(ValidationError):
            mark.save()

    def test_overall_exam_report_calculation(self):
        """Test overall student performance calculation across multiple subjects."""
        StudentExamMark.objects.create(
            student=self.student,
            exam=self.exam,
            subject=self.subject,
            max_marks=50,
            marks_obtained=Decimal("40.00"),
        )
        StudentExamMark.objects.create(
            student=self.student,
            exam=self.exam,
            subject=self.subject2,
            max_marks=50,
            marks_obtained=Decimal("45.00"),
        )
        report = StudentExamMark.get_student_exam_report(self.student, self.exam)
        self.assertIsNotNone(report)
        self.assertEqual(report["total_obtained"], Decimal("85.00"))
        self.assertEqual(report["total_max"], 100)
        self.assertEqual(report["overall_percentage"], 85.0)
        self.assertEqual(report["overall_result"], "Pass")
        self.assertEqual(report["overall_grade"], "A+")

    def test_bulk_marks_entry_by_admin(self):
        """Admin can enter marks in bulk for an exam schedule slot."""
        self.client.force_login(self.admin_user)
        post_data = {
            f"student_{self.student.id}_marks": "42.50",
            f"student_{self.student.id}_remarks": "Great work",
            f"student_{self.student2.id}_marks": "35.00",
            f"student_{self.student2.id}_remarks": "Satisfactory",
        }
        url = reverse("exam_schedule_marks_entry", kwargs={"schedule_id": self.schedule.id})
        response = self.client.post(url, data=post_data, follow=True)
        self.assertEqual(response.status_code, 200)

        mark1 = StudentExamMark.objects.get(student=self.student, exam=self.exam, subject=self.subject)
        self.assertEqual(mark1.marks_obtained, Decimal("42.50"))
        self.assertEqual(mark1.result_status, "Pass")

        mark2 = StudentExamMark.objects.get(student=self.student2, exam=self.exam, subject=self.subject)
        self.assertEqual(mark2.marks_obtained, Decimal("35.00"))
        self.assertEqual(mark2.result_status, "Pass")

    def test_faculty_marks_entry_permission(self):
        """Faculty can only manage marks for their assigned subject."""
        # Faculty 1 is assigned to self.subject
        self.client.force_login(self.faculty_user)
        url = reverse("exam_schedule_marks_entry", kwargs={"schedule_id": self.schedule.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        # Faculty 2 is NOT assigned to self.subject
        self.client.force_login(self.faculty_user2)
        response = self.client.get(url, follow=True)
        self.assertContains(response, "You can only manage marks for your assigned subjects.")

    def test_student_dashboard_exam_results_section(self):
        """Student dashboard displays the Exam Results section with exam, subject, and scores."""
        StudentExamMark.objects.create(
            student=self.student,
            exam=self.exam,
            subject=self.subject,
            max_marks=50,
            marks_obtained=Decimal("44.00"),
        )
        self.client.force_login(self.student_user)
        response = self.client.get(reverse("dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Exam Results")
        self.assertContains(response, self.exam.name)
        self.assertContains(response, self.subject.name)
        self.assertContains(response, "44")

    def test_student_exam_results_portal(self):
        """Student can view their dedicated scorecard at /exams/my-results/."""
        StudentExamMark.objects.create(
            student=self.student,
            exam=self.exam,
            subject=self.subject,
            max_marks=50,
            marks_obtained=Decimal("45.00"),
        )
        self.client.force_login(self.student_user)
        response = self.client.get(reverse("student_exam_results"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "My Examination Results")
        self.assertContains(response, self.exam.name)
        self.assertContains(response, "Overall:")

    def test_exam_marks_dashboard_scoping_and_metrics(self):
        """Verify exam marks dashboard filters by School, Degree, and Class with dynamic metrics."""
        # Create second department, course and student
        dept2 = Department.objects.create(name="School of Mechanical Sciences")
        course2 = Course.objects.create(name="B.Tech Mechanical", department=dept2)
        student2_user = User.objects.create_user(username="mech_st", password="password123")
        student2 = Student.objects.create(
            user=student2_user,
            name="Bob Mech",
            roll_no="MECH001",
            course=course2,
            department=dept2,
            year=1,
            is_approved=True,
        )
        exam2 = Exam.objects.create(
            name="CAT 1 Mechanical",
            exam_type="CAT 1",
            academic_year="2026-2027",
            semester=1,
            course=course2,
            year=1,
            start_date=datetime.date(2026, 10, 10),
            end_date=datetime.date(2026, 10, 20),
            is_active=True,
        )
        subject2 = Subject.objects.create(name="Thermodynamics", code="ME101", course=course2, department=dept2, year=1, semester=1, faculty=self.faculty)

        # Mark 1: Pass
        StudentExamMark.objects.create(
            student=self.student,
            exam=self.exam,
            subject=self.subject,
            max_marks=100,
            marks_obtained=Decimal("75.00"),
            result_status="Pass"
        )
        # Mark 2: Fail
        StudentExamMark.objects.create(
            student=self.student2,
            exam=self.exam,
            subject=self.subject,
            max_marks=100,
            marks_obtained=Decimal("30.00"),
            result_status="Fail"
        )
        # Mark 3 for dept2: Absent
        StudentExamMark.objects.create(
            student=student2,
            exam=exam2,
            subject=subject2,
            max_marks=100,
            marks_obtained=Decimal("0.00"),
            result_status="Absent"
        )

        self.client.force_login(self.admin_user)

        # 1. Unfiltered request -> all 3 marks
        res = self.client.get(reverse("exam_marks_dashboard"))
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.context["total_marks"], 3)
        self.assertEqual(res.context["pass_marks"], 1)
        self.assertEqual(res.context["fail_marks"], 1)
        self.assertEqual(res.context["absent_marks"], 1)

        # 2. Scoped by School 1 -> 2 marks (Pass & Fail)
        res_school1 = self.client.get(reverse("exam_marks_dashboard") + f"?school={self.dept.id}")
        self.assertEqual(res_school1.status_code, 200)
        self.assertEqual(res_school1.context["total_marks"], 2)
        self.assertEqual(res_school1.context["pass_marks"], 1)
        self.assertEqual(res_school1.context["fail_marks"], 1)
        self.assertEqual(res_school1.context["absent_marks"], 0)
        self.assertEqual(res_school1.context["pass_rate"], 50.0)

        # 3. Scoped by School 2 -> 1 mark (Absent)
        res_school2 = self.client.get(reverse("exam_marks_dashboard") + f"?school={dept2.id}&course={course2.id}&year=1")
        self.assertEqual(res_school2.status_code, 200)
        self.assertEqual(res_school2.context["total_marks"], 1)
        self.assertEqual(res_school2.context["pass_marks"], 0)
        self.assertEqual(res_school2.context["fail_marks"], 0)
        self.assertEqual(res_school2.context["absent_marks"], 1)
        self.assertEqual(res_school2.context["pass_rate"], 0.0)

    def test_exam_list_scoping(self):
        """Verify exam_list filters by School, Degree, and Class."""
        dept2 = Department.objects.create(name="School of Commerce")
        course2 = Course.objects.create(name="B.Com General", department=dept2)
        Exam.objects.create(
            name="Commerce CAT",
            exam_type="CAT 2",
            academic_year="2026-2027",
            semester=2,
            course=course2,
            year=1,
            start_date=datetime.date(2026, 11, 1),
            end_date=datetime.date(2026, 11, 10),
            is_active=True,
        )

        self.client.force_login(self.admin_user)
        res_all = self.client.get(reverse("exam_list"))
        self.assertEqual(res_all.status_code, 200)
        self.assertEqual(res_all.context["total_count"], 2)

        res_school = self.client.get(reverse("exam_list") + f"?school={dept2.id}")
        self.assertEqual(res_school.status_code, 200)
        self.assertEqual(res_school.context["total_count"], 1)
        self.assertEqual(len(res_school.context["exams"]), 1)
        self.assertEqual(res_school.context["exams"][0].name, "Commerce CAT")

