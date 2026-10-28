from decimal import Decimal
from django.test import TestCase
from django.contrib.auth.models import User
from students.models import Department, Course, Student
from fees.models import FeeRecord, FeePayment


class FeeOnlinePaymentTestCase(TestCase):
    def setUp(self):
        self.dept = Department.objects.create(name="School of Engineering")
        self.course = Course.objects.create(name="B.Tech CS", department=self.dept)
        self.user = User.objects.create_user(username="feestudent", password="password123")
        self.student = Student.objects.create(
            user=self.user,
            name="Fee Student",
            roll_no="FS001",
            email="fee@college.edu",
            department=self.dept,
            course=self.course,
            year=2,
        )
        self.fee_record = FeeRecord.objects.create(
            student=self.student,
            fee_type="TUITION",
            title="Semester 3 Tuition Fee",
            academic_year="2026-27",
            amount=Decimal("25000.00"),
            status="PENDING",
        )

    def test_pay_fee_ajax_success(self):
        self.client.login(username="feestudent", password="password123")
        response = self.client.post(
            f"/fees/pay/{self.fee_record.id}/",
            {"amount": "10000.00", "payment_mode": "UPI", "reference_number": "UPI/TEST/12345"},
            headers={"x-requested-with": "XMLHttpRequest"},
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["success"])
        self.assertIn("REC-", data["receipt_number"])
        self.assertEqual(data["amount_paid"], 10000.0)
        self.assertEqual(data["remaining_balance"], 15000.0)
        self.assertEqual(data["status"], "PARTIAL")

        self.fee_record.refresh_from_db()
        self.assertEqual(self.fee_record.status, "PARTIAL")
        self.assertEqual(self.fee_record.paid_amount, Decimal("10000.00"))

    def test_pay_fee_full_cleared(self):
        self.client.login(username="feestudent", password="password123")
        response = self.client.post(
            f"/fees/pay/{self.fee_record.id}/",
            {"amount": "25000.00", "payment_mode": "CARD"},
            headers={"x-requested-with": "XMLHttpRequest"},
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["success"])
        self.assertEqual(data["remaining_balance"], 0.0)
        self.assertEqual(data["status"], "PAID")

        self.fee_record.refresh_from_db()
        self.assertEqual(self.fee_record.status, "PAID")
        self.assertEqual(self.fee_record.balance_amount, Decimal("0.00"))

    def test_pay_fee_exceeding_balance_rejected(self):
        self.client.login(username="feestudent", password="password123")
        response = self.client.post(
            f"/fees/pay/{self.fee_record.id}/",
            {"amount": "30000.00", "payment_mode": "UPI"},
            headers={"x-requested-with": "XMLHttpRequest"},
        )
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertFalse(data["success"])
        self.assertIn("exceeds", data["error"])

    def test_pdf_receipt_download_includes_sif(self):
        self.client.login(username="feestudent", password="password123")
        payment = FeePayment.objects.create(
            fee_record=self.fee_record,
            receipt_number="REC-2026-999999",
            amount=Decimal("5000.00"),
            payment_mode="UPI",
            reference_number="UPI/REF/999",
        )
        response = self.client.get(f"/fees/receipt/{payment.id}/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertTrue(len(response.content) > 1000)

    def test_student_dashboard_context_has_fee_summary(self):
        self.client.login(username="feestudent", password="password123")
        response = self.client.get("/students/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("fee_summary", response.context)
        fee_summary = response.context["fee_summary"]
        self.assertEqual(fee_summary["total_amount"], Decimal("25000.00"))
        self.assertEqual(fee_summary["total_balance"], Decimal("25000.00"))
        self.assertTrue(fee_summary["has_pending"])

    def test_admin_dashboard_filter_by_school_degree_class(self):
        # Create second school, degree, student and fee record
        dept2 = Department.objects.create(name="School of Management")
        course2 = Course.objects.create(name="MBA Finance", department=dept2)
        u2 = User.objects.create_user(username="student2", password="password123")
        student2 = Student.objects.create(
            user=u2,
            name="MBA Student",
            roll_no="MBA001",
            email="mba@college.edu",
            department=dept2,
            course=course2,
            year=1,
        )
        fee_record2 = FeeRecord.objects.create(
            student=student2,
            fee_type="TUITION",
            title="MBA Year 1 Fee",
            academic_year="2026-27",
            amount=Decimal("50000.00"),
            status="PENDING",
        )
        FeePayment.objects.create(
            fee_record=fee_record2,
            receipt_number="REC-2026-MBA1",
            amount=Decimal("20000.00"),
            payment_mode="CASH",
        )

        admin_user = User.objects.create_superuser(username="superadmin", password="adminpassword")
        self.client.login(username="superadmin", password="adminpassword")

        # 1. Without filter: All records (25,000 + 50,000 = 75,000 total)
        res_all = self.client.get("/fees/")
        self.assertEqual(res_all.status_code, 200)
        self.assertEqual(res_all.context["total_fee"], Decimal("75000.00"))
        self.assertEqual(res_all.context["total_paid"], Decimal("20000.00"))
        self.assertEqual(res_all.context["total_balance"], Decimal("55000.00"))
        self.assertEqual(res_all.context["record_count"], 2)

        # 2. Filter by School 1 (Engineering)
        res_school1 = self.client.get(f"/fees/?school={self.dept.id}")
        self.assertEqual(res_school1.status_code, 200)
        self.assertEqual(res_school1.context["total_fee"], Decimal("25000.00"))
        self.assertEqual(res_school1.context["total_paid"], Decimal("0.00"))
        self.assertEqual(res_school1.context["total_balance"], Decimal("25000.00"))
        self.assertEqual(res_school1.context["record_count"], 1)

        # 3. Filter by School 2 (Management)
        res_school2 = self.client.get(f"/fees/?school={dept2.id}")
        self.assertEqual(res_school2.status_code, 200)
        self.assertEqual(res_school2.context["total_fee"], Decimal("50000.00"))
        self.assertEqual(res_school2.context["total_paid"], Decimal("20000.00"))
        self.assertEqual(res_school2.context["total_balance"], Decimal("30000.00"))
        self.assertEqual(res_school2.context["record_count"], 1)

        # 4. Filter by Degree (course2)
        res_degree = self.client.get(f"/fees/?school={dept2.id}&course={course2.id}")
        self.assertEqual(res_degree.status_code, 200)
        self.assertEqual(res_degree.context["total_fee"], Decimal("50000.00"))
        self.assertEqual(res_degree.context["record_count"], 1)

        # 5. Filter by Class (year=1 vs year=2)
        res_year1 = self.client.get(f"/fees/?school={dept2.id}&course={course2.id}&year=1")
        self.assertEqual(res_year1.status_code, 200)
        self.assertEqual(res_year1.context["total_fee"], Decimal("50000.00"))
        self.assertEqual(res_year1.context["total_balance"], Decimal("30000.00"))
        self.assertEqual(res_year1.context["record_count"], 1)

        # Year 3 has 0 records under course2
        res_year3 = self.client.get(f"/fees/?school={dept2.id}&course={course2.id}&year=3")
        self.assertEqual(res_year3.status_code, 200)
        self.assertEqual(res_year3.context["total_fee"], Decimal("0.00"))
        self.assertEqual(res_year3.context["total_paid"], Decimal("0.00"))
        self.assertEqual(res_year3.context["total_balance"], Decimal("0.00"))
        self.assertEqual(res_year3.context["record_count"], 0)
