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
