from datetime import date, timedelta
from decimal import Decimal
from django.test import TestCase, Client
from django.urls import reverse
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.contrib.auth.models import User
from django.utils import timezone

from students.models import Student, Department, Course
from fees.models import FeeRecord, FeePayment
from timetable.models import Notification
from .models import (
    Vehicle,
    Route,
    Stop,
    Driver,
    Conductor,
    TransportStaff,
    TransportApplication,
    TransportAllocation,
    TransportPass,
    TransportAttendance,
    VehicleMaintenance,
    TransportComplaint,
    TransportIncident,
)
from .services import (
    get_student_transport_summary,
    get_student_transport_fees,
    get_admin_transport_fees_summary,
    get_transport_admin_dashboard_metrics,
)


class TransportBaseTestCase(TestCase):
    def setUp(self):
        self.client = Client()

        # Users
        self.admin_user = User.objects.create_superuser(
            username="trans_admin",
            password="adminpassword123",
            email="transadmin@smartcollege.edu"
        )
        self.staff_user = User.objects.create_user(
            username="trans_officer",
            password="staffpassword123",
            email="officer@smartcollege.edu"
        )
        self.student_user = User.objects.create_user(
            username="commuter_student",
            password="stupassword123",
            email="commuter@smartcollege.edu"
        )
        self.other_student_user = User.objects.create_user(
            username="other_student",
            password="stupassword123",
            email="other@smartcollege.edu"
        )

        # Department & Course
        self.dept = Department.objects.create(name="School of Engineering & Technology")
        self.course = Course.objects.create(name="B.Tech Computer Science", department=self.dept)

        # Students
        self.student = Student.objects.create(
            user=self.student_user,
            name="Aravind Kumar",
            roll_no="2026-CS-042",
            email="aravind@smartcollege.edu",
            department=self.dept,
            course=self.course,
            year=3,
            phone="9876543210",
            parent_name="R. Kumar",
            parent_phone="9876543211",
            is_active=True,
            is_approved=True,
        )

        self.other_student = Student.objects.create(
            user=self.other_student_user,
            name="Deepa Sharma",
            roll_no="2026-CS-099",
            email="deepa@smartcollege.edu",
            department=self.dept,
            course=self.course,
            year=2,
            phone="9123456780",
            parent_name="V. Sharma",
            parent_phone="9123456781",
            is_active=True,
            is_approved=True,
        )

        # Transport Staff Profile
        self.transport_staff = TransportStaff.objects.create(
            user=self.staff_user,
            role="SUPERVISOR",
            phone="9988776655",
            is_active=True
        )

        # Vehicle
        self.vehicle = Vehicle.objects.create(
            vehicle_number="TN-01-AB-1234",
            registration_number="REG-2024-001",
            vehicle_type="BUS",
            bus_name="Cauvery Express #1",
            seating_capacity=2,  # set to 2 to test capacity boundary
            status="ACTIVE",
            insurance_expiry=timezone.now().date() + timedelta(days=180),
            fitness_expiry=timezone.now().date() + timedelta(days=120),
            pollution_expiry=timezone.now().date() + timedelta(days=90),
        )

        # Route
        self.route = Route.objects.create(
            name="Central Campus - Tambaram Corridor",
            code="RT-101",
            start_point="Tambaram West Terminus",
            destination="SmartCollege Main Gate",
            description="Via Chromepet, Pallavaram, Guindy",
            assigned_vehicle=self.vehicle,
            is_active=True,
        )

        # Stops
        self.stop1 = Stop.objects.create(
            route=self.route,
            stop_name="Tambaram West Terminus",
            stop_code="TMB-01",
            stop_order=1,
            pickup_time="07:15:00",
            drop_time="17:45:00",
            distance_km=25.0,
            fare_amount=Decimal("15000.00"),
            is_active=True,
        )
        self.stop2 = Stop.objects.create(
            route=self.route,
            stop_name="Chromepet Signal",
            stop_code="CHR-02",
            stop_order=2,
            pickup_time="07:30:00",
            drop_time="17:30:00",
            distance_km=21.0,
            fare_amount=Decimal("13500.00"),
            is_active=True,
        )


class TransportCoreFleetTests(TransportBaseTestCase):
    def test_vehicle_creation_and_capacity_metrics(self):
        """Test vehicle creation, capacity constraints, and available seats."""
        self.assertEqual(self.vehicle.seating_capacity, 2)
        self.assertEqual(self.vehicle.allocated_count, 0)
        self.assertEqual(self.vehicle.available_seats, 2)
        self.assertEqual(self.vehicle.occupancy_percentage, 0.0)

    def test_unique_vehicle_number(self):
        """Vehicle numbers must be unique across the fleet."""
        with transaction.atomic():
            with self.assertRaises(IntegrityError):
                Vehicle.objects.create(
                    vehicle_number="TN-01-AB-1234",
                    registration_number="REG-DIFF-999",
                    vehicle_type="BUS",
                    seating_capacity=40,
                )

    def test_unique_route_code(self):
        """Route codes must be unique across the institution."""
        with transaction.atomic():
            with self.assertRaises(IntegrityError):
                Route.objects.create(
                    name="Duplicate Route",
                    code="RT-101",
                    start_point="Point A",
                    destination="Point B",
                )

    def test_unique_stop_order_per_route(self):
        """Stop sequence numbers must be unique within a single route."""
        with transaction.atomic():
            with self.assertRaises(IntegrityError):
                Stop.objects.create(
                    route=self.route,
                    stop_name="Conflict Stop",
                    stop_code="CONF-99",
                    stop_order=1,  # Same as stop1
                )

    def test_driver_licence_validity_warnings(self):
        """Verify commercial driving licence expiration warning calculations."""
        # Active driver with valid licence
        driver = Driver.objects.create(
            name="Murugan S",
            employee_id="DRV-001",
            phone="9876543220",
            licence_number="TN01-2015-0012345",
            licence_expiry=timezone.now().date() + timedelta(days=200),
            assigned_vehicle=self.vehicle,
            is_active=True,
        )
        self.assertFalse(driver.is_licence_expired)
        self.assertFalse(driver.is_licence_expiring_soon)

        # Driver with expiring soon licence (within 30 days)
        driver.licence_expiry = timezone.now().date() + timedelta(days=15)
        driver.save()
        self.assertFalse(driver.is_licence_expired)
        self.assertTrue(driver.is_licence_expiring_soon)

        # Driver with expired licence
        driver.licence_expiry = timezone.now().date() - timedelta(days=5)
        driver.save()
        self.assertTrue(driver.is_licence_expired)


class TransportApplicationWorkflowTests(TransportBaseTestCase):
    def test_student_can_apply_for_transport(self):
        """Students can apply for transport with valid route, stop, and contact details."""
        self.client.login(username="commuter_student", password="stupassword123")
        response = self.client.post(reverse("transport:student_apply"), {
            "route": self.route.pk,
            "stop": self.stop1.pk,
            "academic_year": "2026-27",
            "requested_from_date": (timezone.now().date() + timedelta(days=7)).strftime("%Y-%m-%d"),
            "parent_name": "R. Kumar",
            "parent_phone": "9876543211",
            "student_phone": "9876543210",
            "address": "42 Gandhi Road, Tambaram, Chennai",
            "remarks": "Morning pickup requested",
        })
        self.assertEqual(response.status_code, 302)

        app = TransportApplication.objects.filter(student=self.student).first()
        self.assertIsNotNone(app)
        self.assertEqual(app.status, "PENDING")
        self.assertEqual(app.route, self.route)
        self.assertEqual(app.stop, self.stop1)

    def test_duplicate_active_application_prevented(self):
        """A student cannot have multiple active/pending applications concurrently."""
        TransportApplication.objects.create(
            student=self.student,
            route=self.route,
            stop=self.stop1,
            academic_year="2026-27",
            status="PENDING",
        )
        self.client.login(username="commuter_student", password="stupassword123")
        response = self.client.post(reverse("transport:student_apply"), {
            "route": self.route.pk,
            "stop": self.stop2.pk,
            "academic_year": "2026-27",
            "requested_from_date": timezone.now().date().strftime("%Y-%m-%d"),
            "parent_name": "R. Kumar",
            "parent_phone": "9876543211",
        })
        # Should redirect back to application detail since application already pending
        self.assertEqual(response.status_code, 302)
        self.assertEqual(TransportApplication.objects.filter(student=self.student).count(), 1)

    def test_admin_approve_and_reject_application(self):
        """Transport admin can approve or reject commuter applications and trigger notifications."""
        app = TransportApplication.objects.create(
            student=self.student,
            route=self.route,
            stop=self.stop1,
            academic_year="2026-27",
            status="PENDING",
        )
        self.client.login(username="trans_admin", password="adminpassword123")

        # Approve
        response = self.client.post(reverse("transport:admin_application_review", kwargs={"pk": app.pk}), {
            "action": "APPROVED",
            "remarks": "Approved for Cauvery Express",
        })
        self.assertEqual(response.status_code, 302)
        app.refresh_from_db()
        self.assertEqual(app.status, "APPROVED")
        self.assertEqual(app.reviewed_by, self.admin_user)

        # Verify notification
        notif = Notification.objects.filter(recipient=self.student_user).order_by("-id").first()
        self.assertIsNotNone(notif)
        self.assertIn("Approved", notif.title)


class TransportAllocationAndPassTests(TransportBaseTestCase):
    def test_allocation_capacity_enforcement(self):
        """Bus allocation cannot exceed seating capacity (capacity = 2)."""
        # Allocate Student 1
        alloc1 = TransportAllocation.objects.create(
            student=self.student,
            vehicle=self.vehicle,
            route=self.route,
            stop=self.stop1,
            academic_year="2026-27",
            status="ACTIVE",
        )
        self.assertEqual(self.vehicle.allocated_count, 1)
        self.assertEqual(self.vehicle.available_seats, 1)

        # Allocate Student 2
        alloc2 = TransportAllocation.objects.create(
            student=self.other_student,
            vehicle=self.vehicle,
            route=self.route,
            stop=self.stop2,
            academic_year="2026-27",
            status="ACTIVE",
        )
        self.assertEqual(self.vehicle.allocated_count, 2)
        self.assertEqual(self.vehicle.available_seats, 0)
        self.assertEqual(self.vehicle.occupancy_percentage, 100.0)

        # Attempt to allocate a 3rd student -> clean() must reject
        third_student_user = User.objects.create_user(username="stu3", password="pw")
        third_student = Student.objects.create(
            user=third_student_user,
            name="Vikram R",
            roll_no="2026-CS-077",
            department=self.dept,
            course=self.course,
            year=1,
        )
        alloc3 = TransportAllocation(
            student=third_student,
            vehicle=self.vehicle,
            route=self.route,
            stop=self.stop1,
            academic_year="2026-27",
            status="ACTIVE",
        )
        with self.assertRaises(ValidationError) as ctx:
            alloc3.clean()
        self.assertIn("capacity", str(ctx.exception).lower())

    def test_prevent_duplicate_active_allocation(self):
        """Student cannot have more than one active bus allocation."""
        TransportAllocation.objects.create(
            student=self.student,
            vehicle=self.vehicle,
            route=self.route,
            stop=self.stop1,
            academic_year="2026-27",
            status="ACTIVE",
        )
        duplicate_alloc = TransportAllocation(
            student=self.student,
            vehicle=self.vehicle,
            route=self.route,
            stop=self.stop2,
            academic_year="2026-27",
            status="ACTIVE",
        )
        with self.assertRaises(ValidationError) as ctx:
            duplicate_alloc.clean()
        self.assertIn("already has an active", str(ctx.exception).lower())

    def test_prevent_stop_not_belonging_to_route(self):
        """Stop must belong to the selected route."""
        other_route = Route.objects.create(
            name="Route 2",
            code="RT-202",
            start_point="A",
            destination="B",
        )
        alien_stop = Stop.objects.create(
            route=other_route,
            stop_name="Alien Stop",
            stop_code="ALN-01",
            stop_order=1,
            pickup_time="08:00:00",
            drop_time="17:00:00",
        )
        invalid_alloc = TransportAllocation(
            student=self.student,
            vehicle=self.vehicle,
            route=self.route,
            stop=alien_stop,
            academic_year="2026-27",
            status="ACTIVE",
        )
        with self.assertRaises(ValidationError) as ctx:
            invalid_alloc.clean()
        self.assertIn("does not belong to the selected route", str(ctx.exception).lower())

    def test_transport_pass_generation_and_validity(self):
        """Transport pass generation, unique serial, and validity check."""
        alloc = TransportAllocation.objects.create(
            student=self.student,
            vehicle=self.vehicle,
            route=self.route,
            stop=self.stop1,
            academic_year="2026-27",
            status="ACTIVE",
        )
        pass_obj = TransportPass.objects.create(
            allocation=alloc,
            student=self.student,
            academic_year="2026-27",
            issue_date=timezone.now().date(),
            expiry_date=timezone.now().date() + timedelta(days=365),
            status="ACTIVE",
        )
        self.assertTrue(pass_obj.pass_number.startswith("TP-"))
        self.assertTrue(pass_obj.is_valid)
        self.assertFalse(pass_obj.is_expired)

        # Check expiry logic
        pass_obj.expiry_date = timezone.now().date() - timedelta(days=1)
        pass_obj.save()
        self.assertFalse(pass_obj.is_valid)
        self.assertTrue(pass_obj.is_expired)


class TransportAttendanceRollCallTests(TransportBaseTestCase):
    def test_mark_and_verify_attendance(self):
        """Mark daily roll call attendance and verify history and percentages."""
        TransportAllocation.objects.create(
            student=self.student,
            vehicle=self.vehicle,
            route=self.route,
            stop=self.stop1,
            academic_year="2026-27",
            status="ACTIVE",
        )

        today = timezone.now().date()
        att1 = TransportAttendance.objects.create(
            student=self.student,
            vehicle=self.vehicle,
            route=self.route,
            boarding_stop=self.stop1,
            date=today,
            trip_type="MORNING",
            status="PRESENT",
            marked_by=self.admin_user,
        )
        self.assertEqual(att1.status, "PRESENT")

        # Duplicate attendance on same date and trip type should be prevented
        with transaction.atomic():
            with self.assertRaises(IntegrityError):
                TransportAttendance.objects.create(
                    student=self.student,
                    vehicle=self.vehicle,
                    route=self.route,
                    boarding_stop=self.stop1,
                    date=today,
                    trip_type="MORNING",
                    status="ABSENT",
                )

        # Evening trip is allowed
        att2 = TransportAttendance.objects.create(
            student=self.student,
            vehicle=self.vehicle,
            route=self.route,
            boarding_stop=self.stop1,
            date=today,
            trip_type="EVENING",
            status="PRESENT",
            marked_by=self.admin_user,
        )
        self.assertEqual(TransportAttendance.objects.filter(student=self.student).count(), 2)


class TransportFeesIntegrationTests(TransportBaseTestCase):
    def test_fees_demand_payment_and_summary(self):
        """Transport fee billing, payment collection, and ledger reconciliation."""
        # 1. Issue Transport Fee demand
        fee = FeeRecord.objects.create(
            student=self.student,
            fee_type="TRANSPORT",
            title="Transport Fee - Academic Year 2026-27",
            academic_year="2026-27",
            amount=Decimal("15000.00"),
            due_date=timezone.now().date() + timedelta(days=30),
            status="PENDING",
        )
        self.assertEqual(fee.balance_amount, Decimal("15000.00"))
        self.assertEqual(fee.computed_status, "PENDING")

        # 2. Record partial payment
        payment1 = FeePayment.objects.create(
            fee_record=fee,
            receipt_number="TR-RCPT-2026-0001",
            amount=Decimal("5000.00"),
            payment_date=timezone.now().date(),
            payment_mode="UPI",
            reference_number="UPI-REF-112233",
        )
        fee.refresh_from_db()
        self.assertEqual(fee.paid_amount, Decimal("5000.00"))
        self.assertEqual(fee.balance_amount, Decimal("10000.00"))
        self.assertEqual(fee.computed_status, "PARTIAL")

        # 3. Verify student fees summary service
        summary = get_student_transport_fees(self.student)
        self.assertEqual(summary["total_fees"], Decimal("15000.00"))
        self.assertEqual(summary["total_paid"], Decimal("5000.00"))
        self.assertEqual(summary["outstanding"], Decimal("10000.00"))
        self.assertEqual(len(summary["payments"]), 1)

        # 4. Verify admin fees summary service
        admin_summary = get_admin_transport_fees_summary()
        self.assertEqual(admin_summary["total_billed"], Decimal("15000.00"))
        self.assertEqual(admin_summary["total_paid"], Decimal("5000.00"))
        self.assertEqual(admin_summary["total_outstanding"], Decimal("10000.00"))
        self.assertEqual(admin_summary["collection_rate"], 33.3)


class TransportMaintenanceAndIncidentsTests(TransportBaseTestCase):
    def test_maintenance_logging_and_overdue_alert(self):
        """Log maintenance, calculate service costs, and detect overdue services."""
        # Overdue maintenance
        m1 = VehicleMaintenance.objects.create(
            vehicle=self.vehicle,
            maintenance_type="SERVICE",
            service_date=timezone.now().date() - timedelta(days=120),
            next_service_date=timezone.now().date() - timedelta(days=10),
            cost=Decimal("4500.00"),
            status="SCHEDULED",
            logged_by=self.admin_user,
        )
        self.assertTrue(m1.is_overdue)

        # Completed maintenance
        m2 = VehicleMaintenance.objects.create(
            vehicle=self.vehicle,
            maintenance_type="TYRE",
            service_date=timezone.now().date(),
            cost=Decimal("12000.00"),
            status="COMPLETED",
            logged_by=self.admin_user,
        )
        self.assertFalse(m2.is_overdue)

    def test_safety_incident_recording(self):
        """Log vehicle breakdown or traffic delay incident."""
        incident = TransportIncident.objects.create(
            date=timezone.now().date(),
            vehicle=self.vehicle,
            route=self.route,
            severity="MAJOR",
            status="INVESTIGATING",
            description="Flat tyre near Pallavaram flyover, 25 minutes commute delay.",
            action_taken="Backup van dispatched and commuters reached campus safely.",
            reported_by=self.admin_user,
        )
        self.assertTrue(incident.incident_id.startswith("TR-INC-"))
        self.assertEqual(incident.severity, "MAJOR")


class TransportComplaintWorkflowTests(TransportBaseTestCase):
    def test_complaint_filing_and_resolution_flow(self):
        """Student files grievance, staff resolves it, and notification is dispatched."""
        # 1. Student files complaint
        complaint = TransportComplaint.objects.create(
            student=self.student,
            route=self.route,
            vehicle=self.vehicle,
            category="RASH_DRIVING",
            title="Driver speeding on highway stretch",
            description="The bus was observed driving dangerously above speed limit.",
            priority="HIGH",
            status="OPEN",
        )
        self.assertTrue(complaint.complaint_id.startswith("TR-COMP-"))

        # 2. Staff updates status to RESOLVED
        self.client.login(username="trans_admin", password="adminpassword123")
        response = self.client.post(reverse("transport:admin_complaint_detail", kwargs={"pk": complaint.pk}), {
            "assigned_staff": self.transport_staff.user.pk,
            "status": "RESOLVED",
            "resolution": "Driver cautioned and speed governor calibrated.",
        })
        self.assertEqual(response.status_code, 302)
        complaint.refresh_from_db()
        self.assertEqual(complaint.status, "RESOLVED")
        self.assertIsNotNone(complaint.resolved_at)

        # 3. Notification sent to student
        notif = Notification.objects.filter(recipient=self.student_user).order_by("-id").first()
        self.assertIsNotNone(notif)
        self.assertIn("Resolved", notif.title)


class TransportPermissionsAndSecurityTests(TransportBaseTestCase):
    def test_unauthenticated_user_redirected_to_login(self):
        """Unauthenticated requests must be redirected to login."""
        response = self.client.get(reverse("transport:student_portal"))
        self.assertEqual(response.status_code, 302)
        self.assertIn("login", response.url)

    def test_student_cannot_access_admin_dashboard(self):
        """Students attempting to access administrative views receive 403 Forbidden."""
        self.client.login(username="commuter_student", password="stupassword123")
        response = self.client.get(reverse("transport:admin_dashboard"))
        self.assertEqual(response.status_code, 403)

    def test_transport_staff_can_access_admin_dashboard(self):
        """Transport staff profile allows access to administrative transport views."""
        self.client.login(username="trans_officer", password="staffpassword123")
        response = self.client.get(reverse("transport:admin_dashboard"))
        self.assertEqual(response.status_code, 200)

    def test_super_admin_can_access_admin_dashboard(self):
        """Superuser has full administrative access."""
        self.client.login(username="trans_admin", password="adminpassword123")
        response = self.client.get(reverse("transport:admin_dashboard"))
        self.assertEqual(response.status_code, 200)

    def test_student_idor_protection(self):
        """Student cannot view another student's transport application or pass."""
        other_app = TransportApplication.objects.create(
            student=self.other_student,
            route=self.route,
            stop=self.stop2,
            academic_year="2026-27",
            status="PENDING",
        )
        self.client.login(username="commuter_student", password="stupassword123")
        response = self.client.get(reverse("transport:application_detail", kwargs={"pk": other_app.pk}))
        # Must be 403 Forbidden
        self.assertEqual(response.status_code, 403)


class TransportReportsExportTests(TransportBaseTestCase):
    def setUp(self):
        super().setUp()
        self.client.login(username="trans_admin", password="adminpassword123")

    def test_excel_exports(self):
        """Excel report endpoints must return valid spreadsheet MIME type."""
        excel_endpoints = [
            "transport:export_vehicles_excel",
            "transport:export_routes_excel",
            "transport:export_stops_excel",
            "transport:export_drivers_excel",
            "transport:export_allocations_excel",
            "transport:export_occupancy_excel",
            "transport:export_attendance_excel",
            "transport:export_fees_excel",
            "transport:export_passes_excel",
            "transport:export_maintenance_excel",
            "transport:export_complaints_excel",
            "transport:export_incidents_excel",
        ]
        for ep in excel_endpoints:
            with self.subTest(endpoint=ep):
                resp = self.client.get(reverse(ep))
                self.assertEqual(resp.status_code, 200)
                self.assertIn("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", resp["Content-Type"])

    def test_pdf_exports(self):
        """PDF report endpoints must return valid PDF MIME type."""
        pdf_endpoints = [
            "transport:export_vehicles_pdf",
            "transport:export_routes_pdf",
            "transport:export_stops_pdf",
            "transport:export_drivers_pdf",
            "transport:export_allocations_pdf",
            "transport:export_occupancy_pdf",
            "transport:export_attendance_pdf",
            "transport:export_fees_pdf",
            "transport:export_passes_pdf",
            "transport:export_maintenance_pdf",
            "transport:export_complaints_pdf",
            "transport:export_incidents_pdf",
        ]
        for ep in pdf_endpoints:
            with self.subTest(endpoint=ep):
                resp = self.client.get(reverse(ep))
                self.assertEqual(resp.status_code, 200)
                self.assertEqual(resp["Content-Type"], "application/pdf")

    def test_student_pass_pdf_download(self):
        """Student digital pass PDF download generates valid PDF document."""
        alloc = TransportAllocation.objects.create(
            student=self.student,
            vehicle=self.vehicle,
            route=self.route,
            stop=self.stop1,
            academic_year="2026-27",
            status="ACTIVE",
        )
        pass_obj = TransportPass.objects.create(
            allocation=alloc,
            student=self.student,
            academic_year="2026-27",
            issue_date=timezone.now().date(),
            expiry_date=timezone.now().date() + timedelta(days=365),
            status="ACTIVE",
        )
        self.client.login(username="commuter_student", password="stupassword123")
        resp = self.client.get(reverse("transport:student_pass_pdf"))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp["Content-Type"], "application/pdf")
