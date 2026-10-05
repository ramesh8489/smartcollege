import datetime
from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone
from django.urls import reverse

from students.models import Student, Department, Course
from timetable.models import Notification
from certificates.models import (
    CertificateType,
    CertificateRequest,
    GeneratedCertificate,
    StudentDocument,
)
from certificates.services import (
    seed_default_certificate_types,
    generate_certificate_for_request,
)


class CertificateAndDocumentTestSuite(TestCase):
    """
    Comprehensive verification covering TEST 1 through TEST 26
    for the Certificate & Document Management Module.
    """

    def setUp(self):
        self.client = Client()

        # Seed standard certificate types
        seed_default_certificate_types()
        self.bonafide_type = CertificateType.objects.get(code="BONAFIDE")
        self.tc_type = CertificateType.objects.get(code="TRANSFER")

        # Department & Course
        self.dept = Department.objects.create(name="School of Computing Sciences")
        self.course = Course.objects.create(name="B.Tech Computer Science", department=self.dept)

        # Admin User
        self.admin_user = User.objects.create_superuser(
            username="admin_dean",
            email="dean@smartcollege.edu",
            password="adminpassword123",
        )

        # Student 1 (Alice)
        self.student_user_1 = User.objects.create_user(
            username="student_alice",
            email="alice@smartcollege.edu",
            password="studentpassword123",
        )
        self.student_1 = Student.objects.create(
            user=self.student_user_1,
            name="Alice Smith",
            roll_no="2026CSE001",
            sif_number="SIF-2026-001",
            email="alice@smartcollege.edu",
            department=self.dept,
            course=self.course,
            year=3,
            is_active=True,
            is_approved=True,
        )

        # Student 2 (Bob)
        self.student_user_2 = User.objects.create_user(
            username="student_bob",
            email="bob@smartcollege.edu",
            password="studentpassword123",
        )
        self.student_2 = Student.objects.create(
            user=self.student_user_2,
            name="Bob Jones",
            roll_no="2026CSE002",
            sif_number="SIF-2026-002",
            email="bob@smartcollege.edu",
            department=self.dept,
            course=self.course,
            year=2,
            is_active=True,
            is_approved=True,
        )

    # TEST 1: Student Login
    def test_01_student_login(self):
        logged_in = self.client.login(username="student_alice", password="studentpassword123")
        self.assertTrue(logged_in)
        response = self.client.get("/certificates/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Alice Smith")

    # TEST 2: Student Certificate Request
    def test_02_student_certificate_request(self):
        self.client.login(username="student_alice", password="studentpassword123")
        response = self.client.post("/certificates/request/", {
            "certificate_type": self.bonafide_type.id,
            "purpose": "Bank Education Loan Application",
            "additional_remarks": "Required urgently by Friday",
        }, follow=True)
        self.assertEqual(response.status_code, 200)

        req = CertificateRequest.objects.filter(student=self.student_1).first()
        self.assertIsNotNone(req)
        self.assertTrue(req.request_id.startswith("CERT-REQ-"))
        self.assertEqual(req.status, CertificateRequest.STATUS_PENDING)
        self.assertEqual(req.purpose, "Bank Education Loan Application")

        # Test duplicate prevention for active request of same type
        dup_response = self.client.post("/certificates/request/", {
            "certificate_type": self.bonafide_type.id,
            "purpose": "Another duplicate loan request",
        })
        self.assertContains(dup_response, "already have an active pending request")

    # TEST 3: Admin Sees Request
    def test_03_admin_sees_request(self):
        req = CertificateRequest.objects.create(
            request_id=CertificateRequest.generate_next_request_id(),
            student=self.student_1,
            certificate_type=self.bonafide_type,
            purpose="Passport Verification",
            status=CertificateRequest.STATUS_PENDING,
        )
        self.client.login(username="admin_dean", password="adminpassword123")
        response = self.client.get("/certificates/admin/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, req.request_id)
        self.assertContains(response, "Alice Smith")

    # TEST 4: Admin Changes Status to Under Review
    def test_04_admin_changes_status_to_review(self):
        req = CertificateRequest.objects.create(
            request_id=CertificateRequest.generate_next_request_id(),
            student=self.student_1,
            certificate_type=self.bonafide_type,
            purpose="Visa Application",
            status=CertificateRequest.STATUS_PENDING,
        )
        self.client.login(username="admin_dean", password="adminpassword123")
        response = self.client.post(f"/certificates/detail/{req.pk}/action/", {
            "action": "review",
        }, follow=True)
        self.assertEqual(response.status_code, 200)

        req.refresh_from_db()
        self.assertEqual(req.status, CertificateRequest.STATUS_UNDER_REVIEW)

    # TEST 5 & 6: Admin Rejection with Mandatory Reason Validation
    def test_05_06_admin_rejection_reason_validation(self):
        req = CertificateRequest.objects.create(
            request_id=CertificateRequest.generate_next_request_id(),
            student=self.student_1,
            certificate_type=self.bonafide_type,
            purpose="Incomplete application",
            status=CertificateRequest.STATUS_PENDING,
        )
        self.client.login(username="admin_dean", password="adminpassword123")

        # 1. Attempt rejection without reason -> should fail
        response_fail = self.client.post(f"/certificates/detail/{req.pk}/action/", {
            "action": "reject",
            "rejection_reason": "",
        }, follow=True)
        self.assertContains(response_fail, "rejection reason is mandatory")
        req.refresh_from_db()
        self.assertNotEqual(req.status, CertificateRequest.STATUS_REJECTED)

        # 2. Reject with reason -> should succeed
        response_ok = self.client.post(f"/certificates/detail/{req.pk}/action/", {
            "action": "reject",
            "rejection_reason": "Academic records show pending fees clearance required before issuing bonafide.",
        }, follow=True)
        self.assertEqual(response_ok.status_code, 200)
        req.refresh_from_db()
        self.assertEqual(req.status, CertificateRequest.STATUS_REJECTED)
        self.assertIn("pending fees clearance", req.rejection_reason)

    # TEST 7 & 8: Admin Approves Request & Certificate Number Generation
    def test_07_08_admin_approval_and_cert_number(self):
        req = CertificateRequest.objects.create(
            request_id=CertificateRequest.generate_next_request_id(),
            student=self.student_1,
            certificate_type=self.bonafide_type,
            purpose="Scholarship Verification",
            status=CertificateRequest.STATUS_PENDING,
        )
        self.client.login(username="admin_dean", password="adminpassword123")

        # Approve
        self.client.post(f"/certificates/detail/{req.pk}/action/", {"action": "approve"})
        req.refresh_from_db()
        self.assertEqual(req.status, CertificateRequest.STATUS_APPROVED)
        self.assertEqual(req.approved_by, self.admin_user)

        # Generate Certificate
        cert = generate_certificate_for_request(req, user=self.admin_user)
        self.assertTrue(cert.certificate_number.startswith("SC-CERT-"))
        self.assertEqual(cert.student, self.student_1)
        req.refresh_from_db()
        self.assertEqual(req.status, CertificateRequest.STATUS_GENERATED)

    # TEST 9 & 10: PDF Generation & PDF Download
    def test_09_10_pdf_generation_and_download(self):
        req = CertificateRequest.objects.create(
            request_id=CertificateRequest.generate_next_request_id(),
            student=self.student_1,
            certificate_type=self.bonafide_type,
            purpose="Loan Clearance",
            status=CertificateRequest.STATUS_APPROVED,
        )
        cert = generate_certificate_for_request(req, user=self.admin_user)

        # Student downloads PDF
        self.client.login(username="student_alice", password="studentpassword123")
        response = self.client.get(f"/certificates/download/{req.pk}/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")
        pdf_bytes = b"".join(response.streaming_content) if getattr(response, "streaming", False) else response.content
        self.assertTrue(len(pdf_bytes) > 1000)

        # Download counter and status check
        cert.refresh_from_db()
        self.assertEqual(cert.download_count, 1)
        req.refresh_from_db()
        self.assertEqual(req.status, CertificateRequest.STATUS_DOWNLOADED)

    # TEST 11 & 12: Certificate Verification (Valid & Invalid)
    def test_11_12_certificate_verification(self):
        req = CertificateRequest.objects.create(
            request_id=CertificateRequest.generate_next_request_id(),
            student=self.student_1,
            certificate_type=self.bonafide_type,
            purpose="Public Verification Test",
            status=CertificateRequest.STATUS_APPROVED,
        )
        cert = generate_certificate_for_request(req, user=self.admin_user)

        # Valid certificate verification (unauthenticated public client)
        c_anon = Client()
        response_valid = c_anon.get(f"/certificates/verify/{cert.certificate_number}/")
        self.assertEqual(response_valid.status_code, 200)
        self.assertContains(response_valid, "OFFICIALLY VERIFIED CERTIFICATE")
        self.assertContains(response_valid, "Alice Smith")
        self.assertContains(response_valid, cert.certificate_number)

        # Invalid certificate verification
        response_invalid = c_anon.get("/certificates/verify/SC-CERT-9999-INVALID/")
        self.assertEqual(response_invalid.status_code, 200)
        self.assertContains(response_invalid, "Certificate Not Found")

    # TEST 13 & 14 & 15: Student Document Upload, Verification, and Rejection
    def test_13_14_15_document_upload_and_verification(self):
        # 1. Student uploads document
        self.client.login(username="student_alice", password="studentpassword123")
        dummy_file = SimpleUploadedFile("aadhar_card.pdf", b"%PDF-1.4 dummy file content", content_type="application/pdf")
        response_upload = self.client.post("/documents/", {
            "document_type": StudentDocument.DOC_ID_PROOF,
            "title": "Aadhaar Card Copy",
            "file": dummy_file,
            "remarks": "Uploaded for admission records",
        }, follow=True)
        self.assertEqual(response_upload.status_code, 200)

        doc = StudentDocument.objects.filter(student=self.student_1, title="Aadhaar Card Copy").first()
        self.assertIsNotNone(doc)
        self.assertEqual(doc.verification_status, StudentDocument.STATUS_PENDING)

        # 2. Admin verifies document
        self.client.login(username="admin_dean", password="adminpassword123")
        resp_verify = self.client.post(f"/documents/verify/{doc.pk}/", {
            "verification_status": StudentDocument.STATUS_VERIFIED,
            "remarks": "Identity matched university records.",
        }, follow=True)
        self.assertEqual(resp_verify.status_code, 200)
        doc.refresh_from_db()
        self.assertEqual(doc.verification_status, StudentDocument.STATUS_VERIFIED)

        # 3. Document rejection with reason
        resp_reject = self.client.post(f"/documents/verify/{doc.pk}/", {
            "verification_status": StudentDocument.STATUS_REJECTED,
            "rejection_reason": "Image resolution too low, text unreadable.",
        }, follow=True)
        doc.refresh_from_db()
        self.assertEqual(doc.verification_status, StudentDocument.STATUS_REJECTED)
        self.assertIn("Image resolution too low", doc.rejection_reason)

    # TEST 16 & 17: Secure Student Access & Unauthorized Protection
    def test_16_17_secure_student_isolation_and_unauthorized_access(self):
        # Student 1 document
        dummy_file = SimpleUploadedFile("alice_marks.pdf", b"%PDF-1.4 alice marks", content_type="application/pdf")
        doc_alice = StudentDocument.objects.create(
            student=self.student_1,
            document_type=StudentDocument.DOC_MARKSHEET,
            title="Alice 12th Marksheet",
            file=dummy_file,
            uploaded_by=self.student_user_1,
        )

        # Student 1 certificate
        req_alice = CertificateRequest.objects.create(
            request_id=CertificateRequest.generate_next_request_id(),
            student=self.student_1,
            certificate_type=self.bonafide_type,
            purpose="Alice Private Request",
            status=CertificateRequest.STATUS_APPROVED,
        )
        cert_alice = generate_certificate_for_request(req_alice, user=self.admin_user)

        # Student 2 logs in
        self.client.login(username="student_bob", password="studentpassword123")

        # Bob views portal: should not see Alice's documents
        resp_portal = self.client.get("/documents/")
        self.assertNotContains(resp_portal, "Alice 12th Marksheet")

        # Bob attempts direct download of Alice's document -> 403 Forbidden
        resp_download_doc = self.client.get(f"/documents/download/{doc_alice.pk}/")
        self.assertEqual(resp_download_doc.status_code, 403)

        # Bob attempts direct download of Alice's certificate -> 403 Forbidden
        resp_download_cert = self.client.get(f"/certificates/download/{req_alice.pk}/")
        self.assertEqual(resp_download_cert.status_code, 403)

        # Bob attempts admin dashboard -> 403 Forbidden
        resp_admin = self.client.get("/certificates/admin/")
        self.assertEqual(resp_admin.status_code, 403)

    # TEST 18 & 19: Existing Student & Admin Dashboards
    def test_18_19_existing_dashboards_regression(self):
        # Student Dashboard
        self.client.login(username="student_alice", password="studentpassword123")
        resp_st_dash = self.client.get("/students/")
        self.assertEqual(resp_st_dash.status_code, 200)
        self.assertContains(resp_st_dash, "Certificates & Document Management")

        # Admin Dashboard
        self.client.login(username="admin_dean", password="adminpassword123")
        resp_admin_dash = self.client.get("/accounts/admin-dashboard/")
        self.assertEqual(resp_admin_dash.status_code, 200)
        self.assertContains(resp_admin_dash, "Certificate & Document Management")
