from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.exceptions import ValidationError
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal

from students.models import Department, Course, Student
from faculty.models import Faculty, Subject
from assignments.models import Assignment, AssignmentSubmission


class AssignmentModelTestCase(TestCase):
    def setUp(self):
        self.dept = Department.objects.create(name="School of Computing")
        self.course = Course.objects.create(name="B.Tech Computer Science", department=self.dept)
        self.faculty_user = User.objects.create_user(username="prof_smith", email="smith@college.edu", password="testpassword123")
        self.faculty = Faculty.objects.create(
            user=self.faculty_user,
            faculty_id="FAC999",
            name="Dr. Smith",
            email="smith@college.edu",
            department=self.dept
        )
        self.subject = Subject.objects.create(
            name="Database Systems",
            code="CS301",
            department=self.dept,
            course=self.course,
            faculty=self.faculty
        )
        self.student_user = User.objects.create_user(username="alice", email="alice@college.edu", password="testpassword123")
        self.student = Student.objects.create(
            user=self.student_user,
            name="Alice Walker",
            roll_no="26CS001",
            course=self.course,
            department=self.dept,
            year=2,
            is_approved=True
        )

    def test_assignment_creation_and_properties(self):
        now = timezone.now()
        assignment = Assignment.objects.create(
            title="Lab 1: SQL Basics",
            assignment_type="Lab Record",
            subject=self.subject,
            faculty=self.faculty,
            course=self.course,
            year=2,
            semester=3,
            academic_year="2026-2027",
            assigned_date=now.date(),
            submission_deadline=now + timedelta(days=5),
            max_marks=50,
            instructions="Complete all queries and export results."
        )
        self.assertEqual(assignment.max_marks, 50)
        self.assertFalse(assignment.is_deadline_passed)
        self.assertIn("days remaining", assignment.time_remaining_display)
        self.assertEqual(assignment.submission_count, 0)

    def test_assignment_deadline_validation(self):
        now = timezone.now()
        assignment = Assignment(
            title="Invalid Assignment",
            assignment_type="Homework",
            subject=self.subject,
            faculty=self.faculty,
            course=self.course,
            year=2,
            semester=3,
            academic_year="2026-2027",
            assigned_date=now.date(),
            submission_deadline=now - timedelta(days=2),  # Deadline before assigned_date
            max_marks=20
        )
        with self.assertRaises(ValidationError):
            assignment.clean()

    def test_submission_automatic_status_and_scoring(self):
        now = timezone.now()
        assignment = Assignment.objects.create(
            title="Homework 1: Relational Algebra",
            assignment_type="Homework",
            subject=self.subject,
            faculty=self.faculty,
            course=self.course,
            year=2,
            semester=3,
            academic_year="2026-2027",
            assigned_date=now.date(),
            submission_deadline=now + timedelta(days=2),
            max_marks=100
        )

        test_file = SimpleUploadedFile("solution.pdf", b"%PDF-1.4 Relational Algebra Solution")
        submission = AssignmentSubmission.objects.create(
            assignment=assignment,
            student=self.student,
            submission_file=test_file,
            student_remarks="Completed all 10 problems."
        )

        # Before deadline -> status should be "Submitted"
        self.assertEqual(submission.status, "Submitted")
        self.assertFalse(submission.is_late)
        self.assertEqual(assignment.submission_count, 1)

        # Faculty evaluates submission
        submission.marks_obtained = Decimal("92.50")
        submission.feedback = "Excellent work on equivalence proofs."
        submission.save()

        submission.refresh_from_db()
        self.assertEqual(submission.status, "Evaluated")
        self.assertEqual(submission.percentage, Decimal("92.50"))
        self.assertIsNotNone(submission.evaluated_at)

    def test_submission_marks_exceed_max_marks_raises_error(self):
        now = timezone.now()
        assignment = Assignment.objects.create(
            title="Quiz 1",
            assignment_type="Assignment",
            subject=self.subject,
            faculty=self.faculty,
            course=self.course,
            year=2,
            semester=3,
            academic_year="2026-2027",
            assigned_date=now.date(),
            submission_deadline=now + timedelta(days=3),
            max_marks=20
        )

        test_file = SimpleUploadedFile("answers.txt", b"Quiz answers")
        submission = AssignmentSubmission(
            assignment=assignment,
            student=self.student,
            submission_file=test_file,
            marks_obtained=Decimal("25.00")  # Exceeds max_marks (20)
        )
        with self.assertRaises(ValidationError):
            submission.clean()


class AssignmentViewsTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.dept = Department.objects.create(name="School of Engineering")
        self.course = Course.objects.create(name="B.Tech Computer Science", department=self.dept)

        # Admin user
        self.admin_user = User.objects.create_superuser(username="admin_user", email="admin@college.edu", password="adminpassword123")

        # Faculty user
        self.faculty_user = User.objects.create_user(username="prof_john", email="john@college.edu", password="password123")
        self.faculty = Faculty.objects.create(
            user=self.faculty_user,
            faculty_id="FAC888",
            name="Dr. John",
            email="john@college.edu",
            department=self.dept
        )

        # Another faculty user
        self.other_faculty_user = User.objects.create_user(username="prof_mary", email="mary@college.edu", password="password123")
        self.other_faculty = Faculty.objects.create(
            user=self.other_faculty_user,
            faculty_id="FAC777",
            name="Dr. Mary",
            email="mary@college.edu",
            department=self.dept
        )

        self.subject = Subject.objects.create(name="Algorithms", code="CS202", department=self.dept, course=self.course, faculty=self.faculty)
        self.other_subject = Subject.objects.create(name="Physics", code="PH101", department=self.dept, course=self.course, faculty=self.other_faculty)

        # Student user (Year 2)
        self.student_user = User.objects.create_user(username="bob", email="bob@college.edu", password="password123")
        self.student = Student.objects.create(
            user=self.student_user,
            name="Bob Martin",
            roll_no="26CS002",
            course=self.course,
            department=self.dept,
            year=2,
            is_approved=True
        )

        # Student user (Year 3 - different cohort)
        self.other_student_user = User.objects.create_user(username="charlie", email="charlie@college.edu", password="password123")
        self.other_student = Student.objects.create(
            user=self.other_student_user,
            name="Charlie Brown",
            roll_no="25CS001",
            course=self.course,
            department=self.dept,
            year=3,
            is_approved=True
        )

        now = timezone.now()
        self.assignment = Assignment.objects.create(
            title="Project: Graph Algorithms",
            assignment_type="Project",
            subject=self.subject,
            faculty=self.faculty,
            course=self.course,
            year=2,
            semester=3,
            academic_year="2026-2027",
            assigned_date=now.date(),
            submission_deadline=now + timedelta(days=7),
            max_marks=50,
            instructions="Implement Dijkstra and Prim algorithms."
        )

    def test_assignment_list_view_as_student(self):
        self.client.login(username="bob", password="password123")
        response = self.client.get("/assignments/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Project: Graph Algorithms")

    def test_student_different_cohort_does_not_see_assignment(self):
        self.client.login(username="charlie", password="password123")
        response = self.client.get("/assignments/")
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Project: Graph Algorithms")

    def test_faculty_create_assignment_view(self):
        self.client.login(username="prof_john", password="password123")
        now = timezone.now()
        post_data = {
            "title": "Homework 2: Divide and Conquer",
            "assignment_type": "Homework",
            "subject": self.subject.id,
            "course": self.course.id,
            "year": 2,
            "semester": 3,
            "academic_year": "2026-2027",
            "assigned_date": now.strftime("%Y-%m-%d"),
            "submission_deadline": (now + timedelta(days=5)).strftime("%Y-%m-%dT%H:%M"),
            "max_marks": 25,
            "description": "Solve Master theorem problems.",
            "instructions": "Submit handwritten or typed PDF.",
            "is_active": "on",
        }
        response = self.client.post("/assignments/create/", post_data)
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Assignment.objects.filter(title="Homework 2: Divide and Conquer").exists())

    def test_student_submit_assignment_and_faculty_evaluate(self):
        # 1. Student submits file
        self.client.login(username="bob", password="password123")
        submission_file = SimpleUploadedFile("graph_impl.py", b"def dijkstra(): pass")
        post_data = {
            "submission_file": submission_file,
            "student_remarks": "Implemented Dijkstra with binary heap.",
        }
        response = self.client.post(f"/assignments/{self.assignment.pk}/", post_data)
        self.assertEqual(response.status_code, 302)

        sub = AssignmentSubmission.objects.get(assignment=self.assignment, student=self.student)
        self.assertEqual(sub.status, "Submitted")
        self.assertFalse(sub.is_late)

        # 2. Faculty evaluates the submission
        self.client.login(username="prof_john", password="password123")
        eval_post_data = {
            "marks_obtained": "47.50",
            "feedback": "Clean implementation and great complexity analysis.",
            "status": "Evaluated",
        }
        eval_response = self.client.post(f"/assignments/submission/{sub.pk}/evaluate/", eval_post_data)
        self.assertEqual(eval_response.status_code, 302)

        sub.refresh_from_db()
        self.assertEqual(sub.status, "Evaluated")
        self.assertEqual(sub.marks_obtained, Decimal("47.50"))
        self.assertEqual(sub.percentage, Decimal("95.00"))

        # 3. Student views their evaluated score on student submissions page
        self.client.login(username="bob", password="password123")
        history_response = self.client.get("/assignments/my-submissions/")
        self.assertEqual(history_response.status_code, 200)
        self.assertContains(history_response, "47.5")
        self.assertContains(history_response, "95")

    def test_student_dashboard_displays_assignments(self):
        self.client.login(username="bob", password="password123")
        response = self.client.get("/students/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Assignments & Coursework")
        self.assertContains(response, "Project: Graph Algorithms")

    def test_faculty_dashboard_displays_assignments(self):
        self.client.login(username="prof_john", password="password123")
        response = self.client.get("/faculty/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Assignments & Coursework")
        self.assertContains(response, "Project: Graph Algorithms")


class ExistingModulesRegressionTestCase(TestCase):
    """
    Regression testing for all existing modules specified in requirement 20:
    - Login
    - Student dashboard
    - Faculty dashboard
    - Attendance
    - Marks
    - Fees
    - Library
    - Exams
    - Circulars
    - Notifications
    """
    def setUp(self):
        self.client = Client()
        self.dept = Department.objects.create(name="School of Science")
        self.course = Course.objects.create(name="B.Sc Mathematics", department=self.dept)

        self.faculty_user = User.objects.create_user(username="prof_math", email="math@college.edu", password="password123")
        self.faculty = Faculty.objects.create(
            user=self.faculty_user,
            faculty_id="FAC101",
            name="Prof. Ramanujan",
            email="math@college.edu",
            department=self.dept
        )
        self.subject = Subject.objects.create(
            name="Linear Algebra",
            code="MA101",
            department=self.dept,
            course=self.course,
            faculty=self.faculty
        )

        self.student_user = User.objects.create_user(username="david", email="david@college.edu", password="password123")
        self.student = Student.objects.create(
            user=self.student_user,
            name="David Hilbert",
            roll_no="26MA001",
            course=self.course,
            department=self.dept,
            year=1,
            is_approved=True
        )

    def test_login_module(self):
        response = self.client.get("/accounts/login/")
        self.assertEqual(response.status_code, 200)

    def test_student_dashboard_module(self):
        self.client.login(username="david", password="password123")
        response = self.client.get("/students/")
        self.assertEqual(response.status_code, 200)

    def test_faculty_dashboard_module(self):
        self.client.login(username="prof_math", password="password123")
        response = self.client.get("/faculty/")
        self.assertEqual(response.status_code, 200)

    def test_attendance_module(self):
        self.client.login(username="prof_math", password="password123")
        response = self.client.get("/faculty/attendance/")
        self.assertEqual(response.status_code, 200)

        self.client.login(username="david", password="password123")
        response2 = self.client.get("/students/attendance-history/")
        self.assertEqual(response2.status_code, 200)

    def test_marks_module(self):
        self.client.login(username="prof_math", password="password123")
        response = self.client.get("/faculty/marks/")
        self.assertEqual(response.status_code, 200)

        self.client.login(username="david", password="password123")
        response2 = self.client.get("/students/marks-history/")
        self.assertEqual(response2.status_code, 200)

    def test_fees_module(self):
        self.client.login(username="david", password="password123")
        response = self.client.get("/fees/")
        self.assertEqual(response.status_code, 200)

    def test_library_module(self):
        self.client.login(username="david", password="password123")
        response = self.client.get("/library/")
        self.assertEqual(response.status_code, 200)

    def test_exams_module(self):
        self.client.login(username="david", password="password123")
        response = self.client.get("/exams/")
        self.assertEqual(response.status_code, 200)

        response2 = self.client.get("/exams/my-results/")
        self.assertEqual(response2.status_code, 200)

    def test_circulars_module(self):
        self.client.login(username="david", password="password123")
        response = self.client.get("/timetable/circulars/")
        self.assertEqual(response.status_code, 200)

    def test_notifications_module(self):
        self.client.login(username="david", password="password123")
        response = self.client.get("/timetable/notifications/")
        self.assertEqual(response.status_code, 200)

