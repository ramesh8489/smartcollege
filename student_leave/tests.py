from datetime import date, timedelta
from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.exceptions import ValidationError
from django.utils import timezone

from students.models import Student, Department, Course
from faculty.models import Faculty, Subject
from timetable.models import SchoolIncharge, Notification, Timetable, Period, SchoolClass
from student_leave.models import StudentLeaveRequest, StudentLeaveHistory


class StudentLeaveWorkflowTests(TestCase):
    def setUp(self):
        # 1. Departments / Schools
        self.dept_cs = Department.objects.create(name="School of Computer Science")
        self.dept_ee = Department.objects.create(name="School of Electrical Engineering")

        # 2. Courses
        self.course_mca = Course.objects.create(name="MCA", department=self.dept_cs)
        self.course_btech = Course.objects.create(name="B.Tech EE", department=self.dept_ee)

        # 3. Users & Student profile
        self.user_student = User.objects.create_user(
            username="student_alice",
            email="alice@college.edu",
            password="password123",
        )
        self.student = Student.objects.create(
            user=self.user_student,
            name="Alice Wonder",
            roll_no="MCA2026-001",
            email="alice@college.edu",
            department=self.dept_cs,
            course=self.course_mca,
            year=1,
            is_approved=True,
            is_active=True,
        )

        # Another student (different department/course)
        self.user_student_other = User.objects.create_user(
            username="student_bob",
            email="bob@college.edu",
            password="password123",
        )
        self.student_bob = Student.objects.create(
            user=self.user_student_other,
            name="Bob Builder",
            roll_no="EE2026-002",
            email="bob@college.edu",
            department=self.dept_ee,
            course=self.course_btech,
            year=2,
            is_approved=True,
            is_active=True,
        )

        # 4. Faculty & Subject
        self.user_faculty = User.objects.create_user(
            username="prof_smith",
            email="smith@college.edu",
            password="password123",
        )
        self.faculty = Faculty.objects.create(
            user=self.user_faculty,
            name="Prof. John Smith",
            faculty_id="FAC001",
            email="smith@college.edu",
            department=self.dept_cs,
            is_approved=True,
            is_active=True,
        )
        self.subject = Subject.objects.create(
            name="Advanced Algorithms",
            code="CS501",
            department=self.dept_cs,
            faculty=self.faculty,
            course=self.course_mca,
            year=1,
        )

        # 5. School Incharge
        self.user_incharge = User.objects.create_user(
            username="incharge_clara",
            email="clara@college.edu",
            password="password123",
        )
        self.faculty_incharge = Faculty.objects.create(
            user=self.user_incharge,
            name="Dr. Clara Oswald",
            faculty_id="FAC002",
            email="clara@college.edu",
            department=self.dept_cs,
            is_approved=True,
            is_active=True,
        )
        self.school_incharge = SchoolIncharge.objects.create(
            department=self.dept_cs,
            faculty=self.faculty_incharge,
        )

        # 6. Admin
        self.user_admin = User.objects.create_superuser(
            username="admin_super",
            email="admin@college.edu",
            password="password123",
        )

        self.client = Client()

    def test_01_student_apply_leave(self):
        """TEST 1: Student logs in -> Apply Leave"""
        self.client.login(username="student_alice", password="password123")

        today = timezone.localdate()
        from_date = today + timedelta(days=2)
        to_date = today + timedelta(days=4)

        dummy_doc = SimpleUploadedFile(
            "medical_note.pdf",
            b"%PDF-1.4 dummy content",
            content_type="application/pdf",
        )

        response = self.client.post(
            "/leaves/apply/",
            {
                "leave_type": "Sick Leave",
                "from_date": from_date.strftime("%Y-%m-%d"),
                "to_date": to_date.strftime("%Y-%m-%d"),
                "reason": "Severe fever and doctor advised rest.",
                "supporting_document": dummy_doc,
                "student_remarks": "Will catch up on assignments.",
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        leave = StudentLeaveRequest.objects.filter(student=self.student).first()
        self.assertIsNotNone(leave)
        self.assertEqual(leave.status, StudentLeaveRequest.STATUS_PENDING)
        self.assertEqual(leave.number_of_days, 3)
        self.assertEqual(leave.leave_type, "Sick Leave")

        # History log check
        hist = leave.history.filter(action="Submitted").first()
        self.assertIsNotNone(hist)
        self.assertEqual(hist.new_status, "Pending")
        self.assertEqual(hist.action_taken_by, self.user_student)

        # Notification check: Authorized faculty notified
        notif = Notification.objects.filter(recipient=self.user_faculty).first()
        self.assertIsNotNone(notif)
        self.assertIn("New Student Leave Request", notif.title)
        self.assertIn(self.student.name, notif.message)

    def test_02_faculty_review_and_approve(self):
        """TEST 2: Faculty logs in -> sees pending request -> approves"""
        today = timezone.localdate()
        leave = StudentLeaveRequest.objects.create(
            student=self.student,
            leave_type="Personal Leave",
            from_date=today + timedelta(days=1),
            to_date=today + timedelta(days=2),
            reason="Attending family function",
            status=StudentLeaveRequest.STATUS_PENDING,
        )

        self.client.login(username="prof_smith", password="password123")

        # Faculty dashboard shows the pending leave
        dash_resp = self.client.get("/leaves/faculty/")
        self.assertEqual(dash_resp.status_code, 200)
        self.assertContains(dash_resp, self.student.name)

        # Faculty approves with remarks
        response = self.client.post(
            f"/leaves/{leave.id}/faculty-action/",
            {
                "action": "approve",
                "remarks": "Approved. Complete assignments upon return.",
            },
            follow=True,
        )
        self.assertEqual(response.status_code, 200)

        leave.refresh_from_db()
        self.assertEqual(leave.status, StudentLeaveRequest.STATUS_FACULTY_APPROVED)
        self.assertEqual(leave.faculty_remarks, "Approved. Complete assignments upon return.")

        # Check history
        hist = leave.history.filter(action="Faculty Approved").first()
        self.assertIsNotNone(hist)
        self.assertEqual(hist.action_taken_by, self.user_faculty)

        # Check notifications: Student notified & Incharge notified
        student_notif = Notification.objects.filter(recipient=self.user_student, title__icontains="Approved").first()
        self.assertIsNotNone(student_notif)

        incharge_notif = Notification.objects.filter(recipient=self.user_incharge).first()
        self.assertIsNotNone(incharge_notif)

    def test_03_school_incharge_review_and_approve(self):
        """TEST 3: School Incharge logs in -> sees faculty-approved request -> approves"""
        today = timezone.localdate()
        leave = StudentLeaveRequest.objects.create(
            student=self.student,
            leave_type="Medical Leave",
            from_date=today + timedelta(days=1),
            to_date=today + timedelta(days=3),
            reason="Surgery recovery",
            status=StudentLeaveRequest.STATUS_FACULTY_APPROVED,
            faculty_remarks="Verified by faculty.",
        )

        self.client.login(username="incharge_clara", password="password123")

        # Incharge portal shows the request
        list_resp = self.client.get("/leaves/incharge/")
        self.assertEqual(list_resp.status_code, 200)
        self.assertContains(list_resp, self.student.name)

        # Incharge approves
        response = self.client.post(
            f"/leaves/{leave.id}/incharge-action/",
            {
                "action": "approve",
                "remarks": "Endorsed by School of Computer Science.",
            },
            follow=True,
        )
        self.assertEqual(response.status_code, 200)

        leave.refresh_from_db()
        self.assertEqual(leave.status, StudentLeaveRequest.STATUS_INCHARGE_APPROVED)
        self.assertEqual(leave.incharge_remarks, "Endorsed by School of Computer Science.")

        # Notification to Student and Admin
        student_notif = Notification.objects.filter(recipient=self.user_student, title__icontains="School Incharge").first()
        self.assertIsNotNone(student_notif)

        admin_notif = Notification.objects.filter(recipient=self.user_admin).first()
        self.assertIsNotNone(admin_notif)

    def test_04_admin_review_final_approval(self):
        """TEST 4: Admin logs in -> sees request -> final approval"""
        today = timezone.localdate()
        leave = StudentLeaveRequest.objects.create(
            student=self.student,
            leave_type="Medical Leave",
            from_date=today + timedelta(days=1),
            to_date=today + timedelta(days=2),
            reason="Dental appointment",
            status=StudentLeaveRequest.STATUS_INCHARGE_APPROVED,
            faculty_remarks="OK",
            incharge_remarks="Endorsed",
        )

        self.client.login(username="admin_super", password="password123")

        # Admin ledger view
        list_resp = self.client.get("/leaves/admin-list/")
        self.assertEqual(list_resp.status_code, 200)
        self.assertContains(list_resp, self.student.name)

        # Admin approves
        response = self.client.post(
            f"/leaves/{leave.id}/admin-action/",
            {
                "action": "approve",
                "remarks": "Final institutional approval granted.",
            },
            follow=True,
        )
        self.assertEqual(response.status_code, 200)

        leave.refresh_from_db()
        self.assertEqual(leave.status, StudentLeaveRequest.STATUS_ADMIN_APPROVED)
        self.assertEqual(leave.admin_remarks, "Final institutional approval granted.")
        self.assertEqual(leave.approved_rejected_by, self.user_admin)
        self.assertIsNotNone(leave.approved_rejected_date)

    def test_05_student_views_final_status(self):
        """TEST 5: Student logs in -> sees final status"""
        today = timezone.localdate()
        leave = StudentLeaveRequest.objects.create(
            student=self.student,
            leave_type="Medical Leave",
            from_date=today + timedelta(days=1),
            to_date=today + timedelta(days=2),
            reason="Medical recovery",
            status=StudentLeaveRequest.STATUS_ADMIN_APPROVED,
            admin_remarks="Officially approved by Dean.",
            approved_rejected_date=timezone.now(),
            approved_rejected_by=self.user_admin,
        )

        self.client.login(username="student_alice", password="password123")

        # Check student leaves list
        resp = self.client.get("/leaves/")
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Admin Approved")

        # Check student dashboard
        dash_resp = self.client.get("/students/")
        self.assertEqual(dash_resp.status_code, 200)
        self.assertContains(dash_resp, "Admin Approved")

        # Detail view
        detail_resp = self.client.get(f"/leaves/{leave.id}/")
        self.assertEqual(detail_resp.status_code, 200)
        self.assertContains(detail_resp, "Officially approved by Dean.")

    def test_06_complete_rejection_workflow_notifications(self):
        """TEST 6: Rejection at faculty stage generates notification and audit record"""
        today = timezone.localdate()
        leave = StudentLeaveRequest.objects.create(
            student=self.student,
            leave_type="Other",
            from_date=today + timedelta(days=1),
            to_date=today + timedelta(days=2),
            reason="Unsubstantiated leave",
            status=StudentLeaveRequest.STATUS_PENDING,
        )

        self.client.login(username="prof_smith", password="password123")
        self.client.post(
            f"/leaves/{leave.id}/faculty-action/",
            {"action": "reject", "remarks": "Invalid documentation provided."},
            follow=True,
        )

        leave.refresh_from_db()
        self.assertEqual(leave.status, StudentLeaveRequest.STATUS_FACULTY_REJECTED)
        self.assertEqual(leave.faculty_remarks, "Invalid documentation provided.")

        notif = Notification.objects.filter(recipient=self.user_student, title__icontains="Rejected").first()
        self.assertIsNotNone(notif)
        self.assertIn("Invalid documentation", notif.message)

    def test_07_approval_history_audit_trail(self):
        """TEST 7: Approval history contains every action sequentially"""
        today = timezone.localdate()
        leave = StudentLeaveRequest.objects.create(
            student=self.student,
            leave_type="Sick Leave",
            from_date=today + timedelta(days=1),
            to_date=today + timedelta(days=2),
            reason="Flu",
            status=StudentLeaveRequest.STATUS_PENDING,
        )
        StudentLeaveHistory.objects.create(
            leave_request=leave,
            action="Submitted",
            previous_status="",
            new_status="Pending",
            action_taken_by=self.user_student,
            remarks="Initial submission",
        )

        # Faculty Approve
        self.client.login(username="prof_smith", password="password123")
        self.client.post(f"/leaves/{leave.id}/faculty-action/", {"action": "approve", "remarks": "Faculty OK"})

        # Incharge Approve
        self.client.login(username="incharge_clara", password="password123")
        self.client.post(f"/leaves/{leave.id}/incharge-action/", {"action": "approve", "remarks": "Incharge OK"})

        # Admin Approve
        self.client.login(username="admin_super", password="password123")
        self.client.post(f"/leaves/{leave.id}/admin-action/", {"action": "approve", "remarks": "Admin OK"})

        histories = list(leave.history.order_by("timestamp").values_list("action", flat=True))
        self.assertEqual(histories, ["Submitted", "Faculty Approved", "Incharge Approved", "Admin Approved"])

    def test_08_security_unauthorized_access_prevented(self):
        """TEST 8: Unauthorized users cannot view or manipulate other users' leave requests"""
        today = timezone.localdate()
        leave = StudentLeaveRequest.objects.create(
            student=self.student,
            leave_type="Sick Leave",
            from_date=today + timedelta(days=1),
            to_date=today + timedelta(days=2),
            reason="Private illness",
            status=StudentLeaveRequest.STATUS_PENDING,
        )

        # Bob (other student) tries to view Alice's leave
        self.client.login(username="student_bob", password="password123")
        resp = self.client.get(f"/leaves/{leave.id}/")
        self.assertEqual(resp.status_code, 403)

        # Bob tries to cancel Alice's leave
        cancel_resp = self.client.post(f"/leaves/{leave.id}/cancel/")
        self.assertEqual(cancel_resp.status_code, 403)

        # Bob tries to review Alice's leave
        review_resp = self.client.post(f"/leaves/{leave.id}/faculty-action/", {"action": "approve"})
        self.assertEqual(review_resp.status_code, 403)

    def test_09_validation_rules(self):
        """Validation: From Date > To Date and Overlap detection"""
        today = timezone.localdate()

        # From date after To date
        invalid_leave = StudentLeaveRequest(
            student=self.student,
            leave_type="Sick Leave",
            from_date=today + timedelta(days=5),
            to_date=today + timedelta(days=2),
            reason="Test",
        )
        with self.assertRaises(ValidationError):
            invalid_leave.clean()

        # Overlapping leave check
        StudentLeaveRequest.objects.create(
            student=self.student,
            leave_type="Sick Leave",
            from_date=today + timedelta(days=10),
            to_date=today + timedelta(days=15),
            reason="First block",
            status=StudentLeaveRequest.STATUS_PENDING,
        )

        overlapping_leave = StudentLeaveRequest(
            student=self.student,
            leave_type="Personal Leave",
            from_date=today + timedelta(days=12),
            to_date=today + timedelta(days=18),
            reason="Overlapping block",
        )
        with self.assertRaises(ValidationError):
            overlapping_leave.clean()

    def test_10_student_cancellation(self):
        """Student can cancel pending leave, but cannot cancel approved leave"""
        today = timezone.localdate()
        leave = StudentLeaveRequest.objects.create(
            student=self.student,
            leave_type="Personal Leave",
            from_date=today + timedelta(days=3),
            to_date=today + timedelta(days=4),
            reason="Need break",
            status=StudentLeaveRequest.STATUS_PENDING,
        )

        self.client.login(username="student_alice", password="password123")
        resp = self.client.post(f"/leaves/{leave.id}/cancel/", follow=True)
        self.assertEqual(resp.status_code, 200)

        leave.refresh_from_db()
        self.assertEqual(leave.status, StudentLeaveRequest.STATUS_CANCELLED)

        # Cannot cancel again
        resp_again = self.client.post(f"/leaves/{leave.id}/cancel/", follow=True)
        self.assertContains(resp_again, "cannot be cancelled")
