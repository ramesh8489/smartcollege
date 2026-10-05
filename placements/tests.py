import datetime
from decimal import Decimal
from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone

from students.models import Student, Department, Course
from timetable.models import Notification
from placements.models import (
    Company,
    PlacementDrive,
    PlacementApplication,
    PlacementRound,
    PlacementResult,
    StudentPlacementProfile,
)
from placements.services import check_student_eligibility


class PlacementWorkflowTestSuite(TestCase):
    """
    Comprehensive verification of TEST 1 through TEST 19
    covering the entire Placement Management and Student Portal lifecycle.
    """

    def setUp(self):
        self.client = Client()

        # Department & Course
        self.dept = Department.objects.create(name="Computer Science & Engineering")
        self.course = Course.objects.create(name="B.Tech CSE", department=self.dept)

        # Admin / Placement Officer
        self.admin_user = User.objects.create_superuser(
            username="placement_officer",
            email="officer@smartcollege.edu",
            password="adminpassword123",
        )

        # Eligible Student
        self.student_user = User.objects.create_user(
            username="student_alice",
            email="alice@smartcollege.edu",
            password="studentpassword123",
        )
        self.student = Student.objects.create(
            user=self.student_user,
            name="Alice Walker",
            roll_no="2022CSE001",
            email="alice@smartcollege.edu",
            phone="9876543210",
            department=self.dept,
            course=self.course,
            year=4,
            is_active=True,
            is_approved=True,
        )
        # Profile with 85% aggregate and 0 backlogs
        StudentPlacementProfile.objects.create(
            student=self.student,
            cgpa_or_percentage=Decimal("85.0"),
            active_backlogs=0,
        )

        # Ineligible Student (Low percentage & active backlogs)
        self.ineligible_user = User.objects.create_user(
            username="student_bob",
            email="bob@smartcollege.edu",
            password="studentpassword123",
        )
        self.ineligible_student = Student.objects.create(
            user=self.ineligible_user,
            name="Bob Smith",
            roll_no="2022CSE002",
            email="bob@smartcollege.edu",
            phone="9876543211",
            department=self.dept,
            course=self.course,
            year=4,
            is_active=True,
            is_approved=True,
        )
        StudentPlacementProfile.objects.create(
            student=self.ineligible_student,
            cgpa_or_percentage=Decimal("58.0"),
            active_backlogs=2,
        )

    # ------------------------------------------------------------
    # TEST 1: Admin creates a company
    # ------------------------------------------------------------
    def test_01_admin_creates_company(self):
        self.client.login(username="placement_officer", password="adminpassword123")
        response = self.client.post(
            "/placements/companies/add/",
            data={
                "name": "Google LLC",
                "industry": "Software & Internet",
                "website": "https://careers.google.com",
                "hr_contact_person": "Sundar Recruiting",
                "contact_email": "campus@google.com",
                "contact_phone": "+91 9876500000",
                "address": "Googleplex Campus, Bangalore",
                "description": "Leading global tech company",
                "minimum_qualification": "B.Tech / BE",
                "status": "Active",
            },
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(Company.objects.filter(name="Google LLC").exists())
        company = Company.objects.get(name="Google LLC")
        self.assertEqual(company.industry, "Software & Internet")
        self.assertEqual(company.status, Company.STATUS_ACTIVE)

    # ------------------------------------------------------------
    # TEST 2 & TEST 3: Admin creates drive & configures eligibility
    # ------------------------------------------------------------
    def test_02_and_03_create_drive_and_configure_eligibility(self):
        company = Company.objects.create(
            name="Microsoft",
            industry="Cloud Computing",
            hr_contact_person="Satya Team",
            contact_email="recruitment@microsoft.com",
            contact_phone="9876543210",
            status="Active",
        )

        today = timezone.localdate()
        deadline = today + datetime.timedelta(days=14)
        drive_date = today + datetime.timedelta(days=21)

        self.client.login(username="placement_officer", password="adminpassword123")
        response = self.client.post(
            "/placements/drives/create/",
            data={
                "company": company.pk,
                "job_title": "Software Development Engineer",
                "job_description": "Building cloud applications on Azure.",
                "employment_type": "Full Time",
                "job_location": "Hyderabad",
                "salary_package": "18.5 LPA",
                "salary_lpa": "18.5",
                "minimum_percentage": "70.0",
                "maximum_backlogs": "0",
                "eligible_year": "4",
                "eligible_departments": [self.dept.pk],
                "eligible_courses": [self.course.pk],
                "application_start_date": today.strftime("%Y-%m-%d"),
                "application_deadline": deadline.strftime("%Y-%m-%d"),
                "drive_date": drive_date.strftime("%Y-%m-%d"),
                "drive_location": "Campus Auditorium",
                "vacancies_count": "15",
                "selection_process": "Online Assessment, Technical Interview, HR",
                "status": "Open",
            },
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        drive = PlacementDrive.objects.filter(job_title="Software Development Engineer").first()
        self.assertIsNotNone(drive)
        self.assertEqual(drive.minimum_percentage, Decimal("70.0"))
        self.assertEqual(drive.maximum_backlogs, 0)
        self.assertEqual(drive.eligible_year, 4)

    # ------------------------------------------------------------
    # TEST 4 & TEST 5: Eligible student views placement drive
    # ------------------------------------------------------------
    def test_04_and_05_student_sees_drive_and_eligibility(self):
        company = Company.objects.create(name="Amazon", industry="E-Commerce", status="Active")
        today = timezone.localdate()
        drive = PlacementDrive.objects.create(
            company=company,
            job_title="Associate SDE",
            employment_type="Full Time",
            job_location="Bangalore",
            salary_package="14.0 LPA",
            minimum_percentage=Decimal("70.0"),
            maximum_backlogs=0,
            eligible_year=4,
            application_start_date=today,
            application_deadline=today + datetime.timedelta(days=10),
            drive_date=today + datetime.timedelta(days=15),
            status="Open",
        )
        drive.eligible_departments.add(self.dept)
        drive.eligible_courses.add(self.course)

        # Check eligibility engine
        is_eligible, reasons = check_student_eligibility(self.student, drive)
        self.assertTrue(is_eligible)
        self.assertIn("Eligible", reasons)

        # Login as student
        self.client.login(username="student_alice", password="studentpassword123")
        portal_resp = self.client.get("/placements/student/")
        self.assertEqual(portal_resp.status_code, 200)
        self.assertContains(portal_resp, "Associate SDE")
        self.assertContains(portal_resp, "Amazon")
        self.assertContains(portal_resp, "Eligible")

        # Detail view
        detail_resp = self.client.get(f"/placements/drives/{drive.pk}/")
        self.assertEqual(detail_resp.status_code, 200)
        self.assertContains(detail_resp, "Eligible to Apply")

    # ------------------------------------------------------------
    # TEST 6 & TEST 7: Student applies & duplicate application prevented
    # ------------------------------------------------------------
    def test_06_and_07_student_apply_and_prevent_duplicate(self):
        company = Company.objects.create(name="TCS", industry="IT Services", status="Active")
        today = timezone.localdate()
        drive = PlacementDrive.objects.create(
            company=company,
            job_title="Systems Engineer",
            employment_type="Full Time",
            job_location="Chennai",
            salary_package="7.0 LPA",
            minimum_percentage=Decimal("60.0"),
            maximum_backlogs=0,
            eligible_year=4,
            application_start_date=today,
            application_deadline=today + datetime.timedelta(days=10),
            drive_date=today + datetime.timedelta(days=15),
            status="Open",
        )

        dummy_resume = SimpleUploadedFile("alice_resume.pdf", b"%PDF-1.4 test resume content", content_type="application/pdf")

        self.client.login(username="student_alice", password="studentpassword123")

        # TEST 6: First application succeeds
        apply_resp = self.client.post(
            f"/placements/drives/{drive.pk}/apply/",
            data={
                "resume": dummy_resume,
                "cover_letter": "I am excited to apply for Systems Engineer.",
            },
            follow=True,
        )
        self.assertEqual(apply_resp.status_code, 200)
        self.assertTrue(PlacementApplication.objects.filter(student=self.student, placement_drive=drive).exists())
        app = PlacementApplication.objects.get(student=self.student, placement_drive=drive)
        self.assertEqual(app.status, PlacementApplication.STATUS_APPLIED)

        # TEST 7: Duplicate application attempt
        dummy_resume2 = SimpleUploadedFile("alice_resume2.pdf", b"%PDF-1.4 test resume content", content_type="application/pdf")
        dup_resp = self.client.post(
            f"/placements/drives/{drive.pk}/apply/",
            data={
                "resume": dummy_resume2,
                "cover_letter": "Duplicate attempt",
            },
            follow=True,
        )
        self.assertEqual(dup_resp.status_code, 200)
        # Verify only 1 application exists in DB
        self.assertEqual(PlacementApplication.objects.filter(student=self.student, placement_drive=drive).count(), 1)
        self.assertContains(dup_resp, "You have already applied")

    # ------------------------------------------------------------
    # TEST 8, 9, 10, 11, 12, 13, 14, 15: Full recruitment pipeline
    # ------------------------------------------------------------
    def test_08_to_15_placement_rounds_selection_and_offers(self):
        company = Company.objects.create(name="Infosys", industry="IT Services", status="Active")
        today = timezone.localdate()
        drive = PlacementDrive.objects.create(
            company=company,
            job_title="Specialist Programmer",
            employment_type="Full Time",
            job_location="Bangalore",
            salary_package="9.5 LPA",
            minimum_percentage=Decimal("65.0"),
            maximum_backlogs=0,
            eligible_year=4,
            application_start_date=today,
            application_deadline=today + datetime.timedelta(days=10),
            drive_date=today + datetime.timedelta(days=15),
            status="Open",
        )

        app = PlacementApplication.objects.create(
            student=self.student,
            placement_drive=drive,
            status=PlacementApplication.STATUS_APPLIED,
            eligibility_status=True,
        )

        # TEST 8: Placement officer views application
        self.client.login(username="placement_officer", password="adminpassword123")
        view_app_resp = self.client.get(f"/placements/applications/{app.pk}/")
        self.assertEqual(view_app_resp.status_code, 200)
        self.assertContains(view_app_resp, "Alice Walker")

        # TEST 9: Shortlist student
        shortlist_resp = self.client.post(
            f"/placements/applications/{app.pk}/status/",
            data={"status": "Shortlisted", "remarks": "Profile meets coding standards."},
            follow=True,
        )
        self.assertEqual(shortlist_resp.status_code, 200)
        app.refresh_from_db()
        self.assertEqual(app.status, "Shortlisted")

        # TEST 10: Create interview/placement round
        round_resp = self.client.post(
            f"/placements/applications/{app.pk}/schedule-round/",
            data={
                "round_number": 1,
                "round_name": "Technical Assessment and Coding",
                "round_type": "Coding",
                "scheduled_date": (today + datetime.timedelta(days=2)).strftime("%Y-%m-%d"),
                "start_time": "10:00",
                "end_time": "11:30",
                "location": "Computer Lab 4",
                "interviewer": "Infosys Panel",
                "result": "Pending",
                "score": "",
                "remarks": "Bring College ID card",
            },
            follow=True,
        )
        self.assertEqual(round_resp.status_code, 200)
        app.refresh_from_db()
        self.assertEqual(app.status, PlacementApplication.STATUS_INTERVIEW)
        self.assertEqual(app.rounds.count(), 1)
        round_obj = app.rounds.first()

        # TEST 11: Student sees interview schedule
        self.client.login(username="student_alice", password="studentpassword123")
        student_portal_resp = self.client.get("/placements/student/")
        self.assertEqual(student_portal_resp.status_code, 200)
        self.assertContains(student_portal_resp, "Technical Assessment and Coding")
        self.assertContains(student_portal_resp, "Computer Lab 4")

        # TEST 12: Update round result
        self.client.login(username="placement_officer", password="adminpassword123")
        update_round_resp = self.client.post(
            f"/placements/applications/rounds/{round_obj.pk}/edit/",
            data={
                "round_number": 1,
                "round_name": "Technical Assessment and Coding",
                "round_type": "Coding",
                "scheduled_date": (today + datetime.timedelta(days=2)).strftime("%Y-%m-%d"),
                "start_time": "10:00",
                "end_time": "11:30",
                "location": "Computer Lab 4",
                "interviewer": "Infosys Panel",
                "result": "Passed",
                "score": "95/100",
                "remarks": "Excellent problem-solving skills shown.",
            },
            follow=True,
        )
        self.assertEqual(update_round_resp.status_code, 200)
        round_obj.refresh_from_db()
        self.assertEqual(round_obj.result, "Passed")
        self.assertEqual(round_obj.score, "95/100")

        # TEST 13 & 14: Final selection and recording result
        offer_file = SimpleUploadedFile("offer_letter.pdf", b"%PDF-1.4 official appointment letter", content_type="application/pdf")
        result_resp = self.client.post(
            f"/placements/applications/{app.pk}/record-result/",
            data={
                "result": "Selected",
                "placement_type": "Full Time",
                "job_title": "Specialist Programmer",
                "ctc": "9.5 LPA",
                "joining_date": (today + datetime.timedelta(days=90)).strftime("%Y-%m-%d"),
                "offer_letter": offer_file,
                "remarks": "Selected in top tier hiring bracket.",
            },
            follow=True,
        )
        self.assertEqual(result_resp.status_code, 200)
        app.refresh_from_db()
        self.assertEqual(app.status, "Selected")

        result = PlacementResult.objects.filter(student=self.student, placement_drive=drive).first()
        self.assertIsNotNone(result)
        self.assertEqual(result.result, "Selected")
        self.assertEqual(result.ctc, "9.5 LPA")

        # TEST 15: Student sees final placement information & offer letter
        self.client.login(username="student_alice", password="studentpassword123")
        student_portal_resp2 = self.client.get("/placements/student/")
        self.assertEqual(student_portal_resp2.status_code, 200)
        self.assertContains(student_portal_resp2, "Congratulations, Alice Walker!")
        self.assertContains(student_portal_resp2, "Specialist Programmer")

        # Verify secure offer letter streaming
        offer_download_resp = self.client.get(f"/placements/results/{result.pk}/offer/")
        self.assertEqual(offer_download_resp.status_code, 200)

    # ------------------------------------------------------------
    # TEST 16: Verify Notification Flow
    # ------------------------------------------------------------
    def test_16_notification_flow(self):
        company = Company.objects.create(name="Wipro", industry="IT Services", status="Active")
        today = timezone.localdate()
        drive = PlacementDrive.objects.create(
            company=company,
            job_title="Project Engineer",
            employment_type="Full Time",
            salary_package="6.5 LPA",
            minimum_percentage=Decimal("60.0"),
            maximum_backlogs=0,
            eligible_year=4,
            application_start_date=today,
            application_deadline=today + datetime.timedelta(days=10),
            drive_date=today + datetime.timedelta(days=15),
            status="Open",
        )
        app = PlacementApplication.objects.create(
            student=self.student,
            placement_drive=drive,
            status=PlacementApplication.STATUS_APPLIED,
        )

        # Trigger round schedule notification
        self.client.login(username="placement_officer", password="adminpassword123")
        self.client.post(
            f"/placements/applications/{app.pk}/schedule-round/",
            data={
                "round_number": 1,
                "round_name": "Technical Interview",
                "round_type": "Technical Interview",
                "scheduled_date": (today + datetime.timedelta(days=3)).strftime("%Y-%m-%d"),
                "start_time": "14:00",
                "location": "Virtual Meet",
                "result": "Pending",
            },
        )

        # Verify notification was created in timetable.models.Notification
        student_notifications = Notification.objects.filter(recipient=self.student_user)
        self.assertTrue(student_notifications.exists())
        latest_notif = student_notifications.latest("id")
        self.assertIn("Interview Scheduled", latest_notif.title)

    # ------------------------------------------------------------
    # TEST 17: Ineligible student rejection
    # ------------------------------------------------------------
    def test_17_ineligible_student_rejection(self):
        company = Company.objects.create(name="Oracle", industry="Database", status="Active")
        today = timezone.localdate()
        drive = PlacementDrive.objects.create(
            company=company,
            job_title="Associate Consultant",
            employment_type="Full Time",
            salary_package="12.0 LPA",
            minimum_percentage=Decimal("75.0"),
            maximum_backlogs=0,
            eligible_year=4,
            application_start_date=today,
            application_deadline=today + datetime.timedelta(days=10),
            drive_date=today + datetime.timedelta(days=15),
            status="Open",
        )

        # Student Bob has 58% and 2 backlogs -> Ineligible
        is_eligible, reasons = check_student_eligibility(self.ineligible_student, drive)
        self.assertFalse(is_eligible)
        self.assertTrue(any("below the required 75.0%" in r for r in reasons))
        self.assertTrue(any("2 standing backlog" in r for r in reasons))

        # Attempt application as Bob
        self.client.login(username="student_bob", password="studentpassword123")
        dummy_resume = SimpleUploadedFile("bob_resume.pdf", b"%PDF-1.4 test content", content_type="application/pdf")
        apply_resp = self.client.post(
            f"/placements/drives/{drive.pk}/apply/",
            data={"resume": dummy_resume},
            follow=True,
        )
        self.assertEqual(apply_resp.status_code, 200)
        self.assertFalse(PlacementApplication.objects.filter(student=self.ineligible_student, placement_drive=drive).exists())
        self.assertContains(apply_resp, "Cannot apply")

    # ------------------------------------------------------------
    # TEST 18: Expired or Closed placement drive
    # ------------------------------------------------------------
    def test_18_expired_or_closed_drive(self):
        company = Company.objects.create(name="Cisco", industry="Networking", status="Active")
        today = timezone.localdate()
        # Drive with deadline passed 5 days ago
        expired_drive = PlacementDrive.objects.create(
            company=company,
            job_title="Network Engineer",
            employment_type="Full Time",
            salary_package="11.0 LPA",
            minimum_percentage=Decimal("60.0"),
            maximum_backlogs=0,
            eligible_year=4,
            application_start_date=today - datetime.timedelta(days=20),
            application_deadline=today - datetime.timedelta(days=5),
            drive_date=today + datetime.timedelta(days=2),
            status="Open",
        )

        is_eligible, reasons = check_student_eligibility(self.student, expired_drive)
        self.assertFalse(is_eligible)
        self.assertTrue(any("deadline has passed" in r for r in reasons))

        self.client.login(username="student_alice", password="studentpassword123")
        dummy_resume = SimpleUploadedFile("alice_resume.pdf", b"%PDF-1.4 test content", content_type="application/pdf")
        apply_resp = self.client.post(
            f"/placements/drives/{expired_drive.pk}/apply/",
            data={"resume": dummy_resume},
            follow=True,
        )
        self.assertFalse(PlacementApplication.objects.filter(student=self.student, placement_drive=expired_drive).exists())
        self.assertContains(apply_resp, "Cannot apply")

    # ------------------------------------------------------------
    # TEST 19: Unauthorized access protection
    # ------------------------------------------------------------
    def test_19_unauthorized_access(self):
        # 1. Anonymous user redirected to login
        anon_resp = self.client.get("/placements/companies/add/")
        self.assertEqual(anon_resp.status_code, 302)
        self.assertIn("/accounts/login/", anon_resp.url)

        # 2. Student cannot create companies or drives (Forbidden 403)
        self.client.login(username="student_alice", password="studentpassword123")
        stud_create_comp = self.client.get("/placements/companies/add/")
        self.assertEqual(stud_create_comp.status_code, 403)

        stud_create_drive = self.client.get("/placements/drives/create/")
        self.assertEqual(stud_create_drive.status_code, 403)

        # 3. Student cannot view another student's application dossier
        company = Company.objects.create(name="IBM", industry="IT", status="Active")
        today = timezone.localdate()
        drive = PlacementDrive.objects.create(
            company=company,
            job_title="Developer",
            employment_type="Full Time",
            salary_package="8.0 LPA",
            minimum_percentage=Decimal("60.0"),
            maximum_backlogs=0,
            eligible_year=4,
            application_start_date=today,
            application_deadline=today + datetime.timedelta(days=10),
            drive_date=today + datetime.timedelta(days=15),
            status="Open",
        )
        bob_app = PlacementApplication.objects.create(
            student=self.ineligible_student,
            placement_drive=drive,
            status=PlacementApplication.STATUS_APPLIED,
        )

        # Alice tries to view Bob's dossier
        unauth_dossier = self.client.get(f"/placements/applications/{bob_app.pk}/")
        self.assertEqual(unauth_dossier.status_code, 403)
