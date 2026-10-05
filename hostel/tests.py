from decimal import Decimal
from django.test import TestCase
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.contrib.auth.models import User
from django.utils import timezone
from fees.models import FeeRecord, FeePayment
from .models import (
    Hostel,
    HostelBlock,
    HostelFloor,
    HostelRoom,
    HostelBed,
    HostelApplication,
    HostelAllocation,
    HostelCheckInOut,
    HostelRoomTransfer,
    HostelAttendance,
    HostelComplaint,
    HostelWarden,
    HostelNotice,
    HostelVisitor,
)
from timetable.models import Notification


class HostelCoreStructureTests(TestCase):
    def setUp(self):
        self.admin_user = User.objects.create_superuser(
            username="hostel_admin",
            password="adminpassword123",
            email="admin@smartcollege.edu",
        )
        self.hostel = Hostel.objects.create(
            name="Sir CV Raman Boys Hostel",
            code="CVR-BH",
            hostel_type="BOYS",
            address="Campus West Zone",
            contact_phone="9876543210",
            contact_email="cvr.hostel@smartcollege.edu",
        )
        self.block_a = HostelBlock.objects.create(
            hostel=self.hostel,
            name="Block A",
            code="BLK-A",
        )
        self.floor_1 = HostelFloor.objects.create(
            block=self.block_a,
            name="1st Floor",
            floor_number=1,
        )
        self.room_101 = HostelRoom.objects.create(
            hostel=self.hostel,
            block=self.block_a,
            floor=self.floor_1,
            room_number="101",
            room_type="DOUBLE",
            capacity=2,
            monthly_rent=4500.00,
        )

    def test_core_structure_creation(self):
        """Verify Hostel -> Block -> Floor -> Room -> Beds hierarchy creation."""
        bed1 = HostelBed.objects.create(room=self.room_101, bed_number="B1")
        bed2 = HostelBed.objects.create(room=self.room_101, bed_number="B2")

        self.assertEqual(self.hostel.total_rooms, 1)
        self.assertEqual(self.hostel.total_beds, 2)
        self.assertEqual(self.hostel.available_beds, 2)
        self.assertEqual(self.hostel.occupied_beds, 0)
        self.assertEqual(self.hostel.occupancy_percentage, 0.0)

        # Mark one bed occupied and verify occupancy calculations
        bed1.status = "OCCUPIED"
        bed1.save()

        self.room_101.refresh_from_db()
        self.assertEqual(self.room_101.status, "PARTIALLY_OCCUPIED")
        self.assertEqual(self.hostel.occupied_beds, 1)
        self.assertEqual(self.hostel.occupancy_percentage, 50.0)

        # Mark second bed occupied -> room should become FULL
        bed2.status = "OCCUPIED"
        bed2.save()

        self.room_101.refresh_from_db()
        self.assertEqual(self.room_101.status, "FULL")
        self.assertEqual(self.hostel.occupied_beds, 2)
        self.assertEqual(self.hostel.occupancy_percentage, 100.0)

    def test_unique_constraints(self):
        """Prevent duplicate codes, rooms, and beds."""
        # 1. Duplicate hostel code
        with transaction.atomic():
            with self.assertRaises(IntegrityError):
                Hostel.objects.create(name="Another Hostel", code="CVR-BH", hostel_type="BOYS")

        # 2. Duplicate block code within same hostel
        with transaction.atomic():
            with self.assertRaises(IntegrityError):
                HostelBlock.objects.create(hostel=self.hostel, name="Block A duplicate", code="BLK-A")

        # 3. Duplicate floor number within same block
        with transaction.atomic():
            with self.assertRaises(IntegrityError):
                HostelFloor.objects.create(block=self.block_a, name="1st Floor duplicate", floor_number=1)

        # 4. Duplicate room number within same block
        with transaction.atomic():
            with self.assertRaises(IntegrityError):
                HostelRoom.objects.create(
                    hostel=self.hostel,
                    block=self.block_a,
                    floor=self.floor_1,
                    room_number="101",
                    capacity=2,
                )

        # 5. Duplicate bed number within same room
        HostelBed.objects.create(room=self.room_101, bed_number="B1")
        with transaction.atomic():
            with self.assertRaises(IntegrityError):
                HostelBed.objects.create(room=self.room_101, bed_number="B1")

    def test_bed_capacity_validation(self):
        """Clean method should prevent creating beds exceeding room capacity."""
        HostelBed.objects.create(room=self.room_101, bed_number="B1")
        HostelBed.objects.create(room=self.room_101, bed_number="B2")
        excess_bed = HostelBed(room=self.room_101, bed_number="B3")
        with self.assertRaises(ValidationError):
            excess_bed.clean()

    def test_admin_pages_render(self):
        """Django admin pages for core hostel models should render cleanly."""
        self.client.login(username="hostel_admin", password="adminpassword123")
        for model in ["hostel", "hostelblock", "hostelfloor", "hostelroom", "hostelbed"]:
            resp = self.client.get(f"/admin/hostel/{model}/")
            self.assertEqual(resp.status_code, 200)


class HostelApplicationWorkflowTests(TestCase):
    def setUp(self):
        from students.models import Department, Course, Student

        self.admin = User.objects.create_superuser(
            username="hostel_admin2",
            password="adminpassword123",
            email="admin2@smartcollege.edu",
        )
        self.dept = Department.objects.create(name="School of Engineering")
        self.course = Course.objects.create(name="B.Tech Computer Science", department=self.dept)

        # Student 1
        self.user1 = User.objects.create_user(username="student1", password="password123", email="s1@college.edu")
        self.student1 = Student.objects.create(
            user=self.user1,
            name="Rahul Sharma",
            roll_no="ENG202601",
            department=self.dept,
            course=self.course,
            year=1,
        )

        # Student 2
        self.user2 = User.objects.create_user(username="student2", password="password123", email="s2@college.edu")
        self.student2 = Student.objects.create(
            user=self.user2,
            name="Ananya Verma",
            roll_no="ENG202602",
            department=self.dept,
            course=self.course,
            year=1,
        )

        self.hostel = Hostel.objects.create(
            name="Kalam Boys Hostel",
            code="KBH",
            hostel_type="BOYS",
        )

    def test_student_submit_application(self):
        """Student applies for hostel, generates valid unique ID, and views own application."""
        self.client.login(username="student1", password="password123")
        resp_get = self.client.get("/hostel/applications/create/")
        self.assertEqual(resp_get.status_code, 200)

        post_data = {
            "hostel_preference": self.hostel.id,
            "room_type_preference": "DOUBLE",
            "academic_year": "2026-27",
            "reason": "Hometown is 350 km away",
            "remarks": "Vegetarian mess requested",
        }
        resp_post = self.client.post("/hostel/applications/create/", post_data)
        self.assertEqual(resp_post.status_code, 302)

        app = HostelApplication.objects.filter(student=self.student1).first()
        self.assertIsNotNone(app)
        self.assertTrue(app.application_id.startswith("HOSTEL-APP-"))
        self.assertEqual(app.status, "PENDING")

        # Student can view own application detail
        resp_detail = self.client.get(f"/hostel/applications/{app.pk}/")
        self.assertEqual(resp_detail.status_code, 200)
        self.assertContains(resp_detail, "HOSTEL-APP-")
        self.assertContains(resp_detail, "Hometown is 350 km away")

    def test_security_student_isolation(self):
        """Student 2 must NOT access Student 1's application."""
        app = HostelApplication.objects.create(
            student=self.student1,
            hostel_preference=self.hostel,
            room_type_preference="SINGLE",
        )

        self.client.login(username="student2", password="password123")
        resp = self.client.get(f"/hostel/applications/{app.pk}/")
        self.assertEqual(resp.status_code, 403)

    def test_admin_review_workflow(self):
        """Admin reviews application: approve and reject with mandatory reason."""
        app1 = HostelApplication.objects.create(
            student=self.student1,
            hostel_preference=self.hostel,
            room_type_preference="DOUBLE",
        )
        app2 = HostelApplication.objects.create(
            student=self.student2,
            hostel_preference=self.hostel,
            room_type_preference="DOUBLE",
        )

        self.client.login(username="hostel_admin2", password="adminpassword123")

        # 1. Admin views application list
        resp_list = self.client.get("/hostel/admin/applications/")
        self.assertEqual(resp_list.status_code, 200)
        self.assertContains(resp_list, app1.application_id)

        # 2. Approve app1
        resp_approve = self.client.post(
            f"/hostel/admin/applications/{app1.pk}/review/",
            {"action": "APPROVED", "remarks": "Approved on merit."},
        )
        self.assertEqual(resp_approve.status_code, 302)
        app1.refresh_from_db()
        self.assertEqual(app1.status, "APPROVED")
        self.assertEqual(app1.reviewed_by, self.admin)
        self.assertIsNotNone(app1.reviewed_date)

        # 3. Reject app2 WITHOUT reason -> should fail validation
        resp_reject_invalid = self.client.post(
            f"/hostel/admin/applications/{app2.pk}/review/",
            {"action": "REJECTED", "remarks": "No capacity", "rejection_reason": ""},
        )
        self.assertEqual(resp_reject_invalid.status_code, 200)
        app2.refresh_from_db()
        self.assertEqual(app2.status, "PENDING")

        # 4. Reject app2 WITH reason -> succeeds
        resp_reject_valid = self.client.post(
            f"/hostel/admin/applications/{app2.pk}/review/",
            {"action": "REJECTED", "remarks": "Review complete", "rejection_reason": "No vacant rooms in Kalam Hostel."},
        )
        self.assertEqual(resp_reject_valid.status_code, 302)
        app2.refresh_from_db()
        self.assertEqual(app2.status, "REJECTED")
        self.assertEqual(app2.rejection_reason, "No vacant rooms in Kalam Hostel.")


class HostelAllocationTests(TestCase):
    def setUp(self):
        from students.models import Department, Course, Student

        self.admin = User.objects.create_superuser(
            username="alloc_admin",
            password="adminpassword123",
            email="alloc_admin@college.edu",
        )
        self.dept = Department.objects.create(name="School of Science")
        self.course = Course.objects.create(name="B.Sc Physics", department=self.dept)

        self.student1 = Student.objects.create(
            name="Vikram Singh",
            roll_no="SCI202601",
            department=self.dept,
            course=self.course,
            year=1,
        )
        self.student2 = Student.objects.create(
            name="Pooja Patel",
            roll_no="SCI202602",
            department=self.dept,
            course=self.course,
            year=1,
        )

        self.hostel = Hostel.objects.create(name="Tagore Hostel", code="TH", hostel_type="BOYS")
        self.block = HostelBlock.objects.create(hostel=self.hostel, name="Block 1", code="B1")
        self.floor = HostelFloor.objects.create(block=self.block, name="Ground Floor", floor_number=0)
        self.room = HostelRoom.objects.create(
            hostel=self.hostel,
            block=self.block,
            floor=self.floor,
            room_number="G-01",
            capacity=2,
            monthly_rent=5000.00,
        )
        self.bed1 = HostelBed.objects.create(room=self.room, bed_number="Bed-A")
        self.bed2 = HostelBed.objects.create(room=self.room, bed_number="Bed-B")

    def test_allocation_lifecycle_and_occupancy(self):
        """Allocate student to bed -> bed becomes occupied -> room occupancy updates."""
        self.assertEqual(self.bed1.status, "AVAILABLE")
        self.assertEqual(self.room.available_beds_count, 2)
        self.assertEqual(self.room.occupied_beds_count, 0)
        self.assertEqual(self.room.status, "AVAILABLE")

        alloc = HostelAllocation.objects.create(
            student=self.student1,
            hostel=self.hostel,
            block=self.block,
            floor=self.floor,
            room=self.room,
            bed=self.bed1,
            allocated_by=self.admin,
        )

        self.assertTrue(alloc.allocation_id.startswith("HOSTEL-ALLOC-"))
        self.assertEqual(alloc.status, "ACTIVE")

        # Verify bed is marked occupied
        self.bed1.refresh_from_db()
        self.assertEqual(self.bed1.status, "OCCUPIED")

        # Verify room occupancy updated
        self.room.refresh_from_db()
        self.assertEqual(self.room.occupied_beds_count, 1)
        self.assertEqual(self.room.available_beds_count, 1)
        self.assertEqual(self.room.status, "PARTIALLY_OCCUPIED")

    def test_prevent_duplicate_student_allocation(self):
        """Same student cannot have two active allocations."""
        HostelAllocation.objects.create(
            student=self.student1,
            hostel=self.hostel,
            block=self.block,
            floor=self.floor,
            room=self.room,
            bed=self.bed1,
        )

        second_alloc = HostelAllocation(
            student=self.student1,
            hostel=self.hostel,
            block=self.block,
            floor=self.floor,
            room=self.room,
            bed=self.bed2,
        )
        with self.assertRaises(ValidationError):
            second_alloc.full_clean()

        with transaction.atomic():
            with self.assertRaises(IntegrityError):
                second_alloc.save()

    def test_prevent_duplicate_bed_allocation(self):
        """Same bed cannot have two active allocations."""
        HostelAllocation.objects.create(
            student=self.student1,
            hostel=self.hostel,
            block=self.block,
            floor=self.floor,
            room=self.room,
            bed=self.bed1,
        )

        dup_bed_alloc = HostelAllocation(
            student=self.student2,
            hostel=self.hostel,
            block=self.block,
            floor=self.floor,
            room=self.room,
            bed=self.bed1,
        )
        with self.assertRaises(ValidationError):
            dup_bed_alloc.full_clean()

        with transaction.atomic():
            with self.assertRaises(IntegrityError):
                dup_bed_alloc.save()

    def test_admin_allocation_views(self):
        """Admin can list and view allocation details."""
        alloc = HostelAllocation.objects.create(
            student=self.student1,
            hostel=self.hostel,
            block=self.block,
            floor=self.floor,
            room=self.room,
            bed=self.bed1,
            allocated_by=self.admin,
        )

        self.client.login(username="alloc_admin", password="adminpassword123")
        resp_list = self.client.get("/hostel/admin/allocations/")
        self.assertEqual(resp_list.status_code, 200)
        self.assertContains(resp_list, alloc.allocation_id)
        self.assertContains(resp_list, "Vikram Singh")

        resp_detail = self.client.get(f"/hostel/admin/allocations/{alloc.pk}/")
        self.assertEqual(resp_detail.status_code, 200)
        self.assertContains(resp_detail, "Room G-01")
        self.assertContains(resp_detail, "Bed-A")


class HostelLifecycleTests(TestCase):
    def setUp(self):
        from students.models import Department, Course, Student

        self.admin = User.objects.create_superuser(
            username="lifecycle_admin",
            password="adminpassword123",
            email="lifecycle_admin@college.edu",
        )
        self.dept = Department.objects.create(name="School of Management")
        self.course = Course.objects.create(name="MBA Finance", department=self.dept)
        self.student = Student.objects.create(
            name="Sneha Reddy",
            roll_no="MBA202601",
            department=self.dept,
            course=self.course,
            year=1,
        )

        self.hostel = Hostel.objects.create(name="Sarojini Girls Hostel", code="SGH", hostel_type="GIRLS")
        self.block = HostelBlock.objects.create(hostel=self.hostel, name="Block A", code="BA")
        self.floor = HostelFloor.objects.create(block=self.block, name="1st Floor", floor_number=1)
        self.room = HostelRoom.objects.create(
            hostel=self.hostel,
            block=self.block,
            floor=self.floor,
            room_number="102",
            capacity=1,
            monthly_rent=6000.00,
        )
        self.bed = HostelBed.objects.create(room=self.room, bed_number="Bed-102A")

    def test_allocation_checkin_checkout_lifecycle(self):
        """Allocation -> Check-in -> Check-out. Verify bed becomes available and history is preserved."""
        # 1. Allocate
        alloc = HostelAllocation.objects.create(
            student=self.student,
            hostel=self.hostel,
            block=self.block,
            floor=self.floor,
            room=self.room,
            bed=self.bed,
            allocated_by=self.admin,
        )
        self.bed.refresh_from_db()
        self.assertEqual(self.bed.status, "OCCUPIED")
        self.room.refresh_from_db()
        self.assertEqual(self.room.status, "FULL")

        self.client.login(username="lifecycle_admin", password="adminpassword123")

        # 2. Check-in event
        resp_checkin = self.client.post(
            f"/hostel/admin/allocations/{alloc.pk}/event/",
            {"event_type": "CHECK_IN", "event_date": "2026-08-01", "remarks": "Luggage checked in, room key issued."},
        )
        self.assertEqual(resp_checkin.status_code, 302)
        self.assertEqual(alloc.lifecycle_events.count(), 1)
        event_in = alloc.lifecycle_events.first()
        self.assertEqual(event_in.event_type, "CHECK_IN")

        # 3. Check-out event
        resp_checkout = self.client.post(
            f"/hostel/admin/allocations/{alloc.pk}/event/",
            {"event_type": "CHECK_OUT", "event_date": "2026-10-04", "reason": "Completed semester exams", "remarks": "Room key returned, no inventory damage."},
        )
        self.assertEqual(resp_checkout.status_code, 302)

        # Verify allocation status updated
        alloc.refresh_from_db()
        self.assertEqual(alloc.status, "CHECKED_OUT")
        self.assertIsNotNone(alloc.actual_checkout_date)

        # Verify bed is released and available again
        self.bed.refresh_from_db()
        self.assertEqual(self.bed.status, "AVAILABLE")

        # Verify room occupancy updated
        self.room.refresh_from_db()
        self.assertEqual(self.room.status, "AVAILABLE")
        self.assertEqual(self.room.available_beds_count, 1)

        # Verify history is preserved
        self.assertEqual(alloc.lifecycle_events.count(), 2)
        event_out = alloc.lifecycle_events.filter(event_type="CHECK_OUT").first()
        self.assertEqual(event_out.reason, "Completed semester exams")


class HostelRoomTransferTests(TestCase):
    def setUp(self):
        from students.models import Department, Course, Student

        self.admin = User.objects.create_superuser(
            username="transfer_admin",
            password="adminpassword123",
            email="transfer_admin@college.edu",
        )
        self.dept = Department.objects.create(name="School of Engineering")
        self.course = Course.objects.create(name="B.Tech CS", department=self.dept)
        self.student = Student.objects.create(
            name="Rohit Mehra",
            roll_no="ENG202699",
            department=self.dept,
            course=self.course,
            year=2,
        )

        self.hostel = Hostel.objects.create(name="Bhabha Hostel", code="BHB", hostel_type="BOYS")
        self.block1 = HostelBlock.objects.create(hostel=self.hostel, name="Block 1", code="B1")
        self.floor1 = HostelFloor.objects.create(block=self.block1, name="1st Floor", floor_number=1)
        self.room_101 = HostelRoom.objects.create(
            hostel=self.hostel,
            block=self.block1,
            floor=self.floor1,
            room_number="101",
            capacity=1,
            monthly_rent=4000.00,
        )
        self.bed_01 = HostelBed.objects.create(room=self.room_101, bed_number="01")

        self.block2 = HostelBlock.objects.create(hostel=self.hostel, name="Block 2", code="B2")
        self.floor2 = HostelFloor.objects.create(block=self.block2, name="2nd Floor", floor_number=2)
        self.room_205 = HostelRoom.objects.create(
            hostel=self.hostel,
            block=self.block2,
            floor=self.floor2,
            room_number="205",
            capacity=1,
            monthly_rent=4500.00,
        )
        self.bed_03 = HostelBed.objects.create(room=self.room_205, bed_number="03")

    def test_room_transfer_workflow(self):
        """Room 101 Bed 01 -> Room 205 Bed 03. Verify both bed and room statuses update atomically."""
        alloc = HostelAllocation.objects.create(
            student=self.student,
            hostel=self.hostel,
            block=self.block1,
            floor=self.floor1,
            room=self.room_101,
            bed=self.bed_01,
            allocated_by=self.admin,
        )
        self.bed_01.refresh_from_db()
        self.assertEqual(self.bed_01.status, "OCCUPIED")
        self.bed_03.refresh_from_db()
        self.assertEqual(self.bed_03.status, "AVAILABLE")

        self.client.login(username="transfer_admin", password="adminpassword123")

        # Submit transfer via UI endpoint
        post_data = {
            "new_hostel": self.hostel.id,
            "new_room": self.room_205.id,
            "new_bed": self.bed_03.id,
            "transfer_date": "2026-10-04",
            "reason": "Requested relocation closer to labs",
            "remarks": "Keys exchanged with warden.",
        }
        resp = self.client.post(f"/hostel/admin/allocations/{alloc.pk}/transfer/", post_data)
        self.assertEqual(resp.status_code, 302)

        # 1. Verify old bed 01 is now AVAILABLE
        self.bed_01.refresh_from_db()
        self.assertEqual(self.bed_01.status, "AVAILABLE")
        self.room_101.refresh_from_db()
        self.assertEqual(self.room_101.status, "AVAILABLE")

        # 2. Verify new bed 03 is now OCCUPIED
        self.bed_03.refresh_from_db()
        self.assertEqual(self.bed_03.status, "OCCUPIED")
        self.room_205.refresh_from_db()
        self.assertEqual(self.room_205.status, "FULL")

        # 3. Verify allocation points to Room 205 Bed 03
        alloc.refresh_from_db()
        self.assertEqual(alloc.room, self.room_205)
        self.assertEqual(alloc.bed, self.bed_03)

        # 4. Verify transfer record is preserved
        self.assertEqual(alloc.transfers.count(), 1)
        transfer = alloc.transfers.first()
        self.assertEqual(transfer.old_room, self.room_101)
        self.assertEqual(transfer.new_room, self.room_205)
        self.assertEqual(transfer.old_bed, self.bed_01)
        self.assertEqual(transfer.new_bed, self.bed_03)
        self.assertEqual(transfer.reason, "Requested relocation closer to labs")


class HostelFeesIntegrationTests(TestCase):
    def setUp(self):
        from students.models import Department, Course, Student
        self.admin = User.objects.create_superuser(
            username="fee_admin",
            password="adminpassword123",
            email="feeadmin@smartcollege.edu",
        )
        self.student_user = User.objects.create_user(
            username="feestudent",
            password="studentpassword123",
            email="feestudent@smartcollege.edu",
        )
        self.dept = Department.objects.create(name="School of Computing")
        self.course = Course.objects.create(name="B.Tech Computer Science", department=self.dept)
        self.student = Student.objects.create(
            user=self.student_user,
            name="Rahul Sharma",
            roll_no="CS2026-FEE01",
            sif_number="SIF-FEE-001",
            email="feestudent@smartcollege.edu",
            department=self.dept,
            course=self.course,
            year=1,
            is_active=True,
        )
        self.hostel = Hostel.objects.create(
            name="Kalam Hostel",
            code="KLM-H",
            hostel_type="BOYS",
            address="Campus Block",
        )

    def test_hostel_fee_creation_and_due_calculation(self):
        """Verify fee creation using existing FeeRecord with fee_type='HOSTEL'."""
        fee = FeeRecord.objects.create(
            student=self.student,
            fee_type="HOSTEL",
            title="Hostel - Mess Fee",
            academic_year="2026-27",
            amount=Decimal("12000.00"),
            status="PENDING",
        )
        self.assertEqual(fee.balance_amount, Decimal("12000.00"))
        self.assertEqual(fee.paid_amount, Decimal("0.00"))
        self.assertEqual(fee.computed_status, "PENDING")

        # Test partial payment
        payment1 = FeePayment.objects.create(
            fee_record=fee,
            receipt_number="REC-HST-001",
            amount=Decimal("5000.00"),
            payment_mode="UPI",
            reference_number="UPI-REF-999888",
        )
        fee.refresh_from_db()
        self.assertEqual(fee.paid_amount, Decimal("5000.00"))
        self.assertEqual(fee.balance_amount, Decimal("7000.00"))
        self.assertEqual(fee.status, "PARTIAL")

        # Test full payment
        payment2 = FeePayment.objects.create(
            fee_record=fee,
            receipt_number="REC-HST-002",
            amount=Decimal("7000.00"),
            payment_mode="BANK",
            reference_number="NEFT-REF-111222",
        )
        fee.refresh_from_db()
        self.assertEqual(fee.paid_amount, Decimal("12000.00"))
        self.assertEqual(fee.balance_amount, Decimal("0.00"))
        self.assertEqual(fee.status, "PAID")

    def test_existing_pdf_receipt_generation_for_hostel_fee(self):
        """Verify that existing fees:payment_receipt view generates PDF receipt for hostel payment."""
        fee = FeeRecord.objects.create(
            student=self.student,
            fee_type="HOSTEL",
            title="Hostel - Hostel Rent",
            academic_year="2026-27",
            amount=Decimal("8000.00"),
        )
        payment = FeePayment.objects.create(
            fee_record=fee,
            receipt_number="REC-HST-PDF-01",
            amount=Decimal("8000.00"),
            payment_mode="CASH",
        )

        self.client.login(username="feestudent", password="studentpassword123")
        resp = self.client.get(f"/fees/receipt/{payment.id}/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp["Content-Type"], "application/pdf")
        self.assertIn("receipt-REC-HST-PDF-01.pdf", resp["Content-Disposition"])

    def test_student_hostel_fees_view(self):
        """Verify student hostel fees portal at /hostel/fees/."""
        FeeRecord.objects.create(
            student=self.student,
            fee_type="HOSTEL",
            title="Hostel - Maintenance Fee",
            academic_year="2026-27",
            amount=Decimal("2500.00"),
        )

        self.client.login(username="feestudent", password="studentpassword123")
        resp = self.client.get("/hostel/fees/")
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Hostel - Maintenance Fee")
        self.assertContains(resp, "2500.00")
        self.assertContains(resp, "Pending")

    def test_admin_create_hostel_fee_endpoint(self):
        """Verify admin can issue hostel fee demand via /hostel/admin/fees/create/."""
        self.client.login(username="fee_admin", password="adminpassword123")
        post_data = {
            "student": self.student.id,
            "fee_subtype": "Security Deposit",
            "amount": "5000.00",
            "academic_year": "2026-27",
            "due_date": "2026-11-01",
            "remarks": "Refundable security deposit.",
        }
        resp = self.client.post("/hostel/admin/fees/create/", post_data)
        self.assertEqual(resp.status_code, 302)

        record = FeeRecord.objects.filter(student=self.student, fee_type="HOSTEL", title="Hostel - Security Deposit").first()
        self.assertIsNotNone(record)
        self.assertEqual(record.amount, Decimal("5000.00"))
        self.assertEqual(record.remarks, "Refundable security deposit.")


class HostelAttendanceTests(TestCase):
    def setUp(self):
        from students.models import Department, Course, Student
        self.admin = User.objects.create_superuser(
            username="warden_att",
            password="adminpassword123",
            email="warden@smartcollege.edu",
        )
        self.dept = Department.objects.create(name="School of Sciences")
        self.course = Course.objects.create(name="B.Sc Physics", department=self.dept)

        self.u1 = User.objects.create_user(username="res1", password="pass123", email="res1@college.edu")
        self.student1 = Student.objects.create(
            user=self.u1, name="Amit Kumar", roll_no="PH2026-01",
            department=self.dept, course=self.course, year=1, is_active=True,
        )

        self.u2 = User.objects.create_user(username="res2", password="pass123", email="res2@college.edu")
        self.student2 = Student.objects.create(
            user=self.u2, name="Priya Singh", roll_no="PH2026-02",
            department=self.dept, course=self.course, year=1, is_active=True,
        )

        self.hostel = Hostel.objects.create(
            name="Tagore Hostel", code="TGR-H", hostel_type="BOYS", address="Campus North",
        )
        self.block = HostelBlock.objects.create(hostel=self.hostel, name="Block A", code="BA")
        self.floor = HostelFloor.objects.create(block=self.block, name="1st Floor", floor_number=1)
        self.room = HostelRoom.objects.create(
            hostel=self.hostel, block=self.block, floor=self.floor, room_number="101", capacity=2,
        )
        self.bed1 = HostelBed.objects.create(room=self.room, bed_number="B1")
        self.bed2 = HostelBed.objects.create(room=self.room, bed_number="B2")

        # Active allocations
        self.alloc1 = HostelAllocation.objects.create(
            student=self.student1, hostel=self.hostel, block=self.block, floor=self.floor,
            room=self.room, bed=self.bed1, allocated_by=self.admin,
        )
        self.alloc2 = HostelAllocation.objects.create(
            student=self.student2, hostel=self.hostel, block=self.block, floor=self.floor,
            room=self.room, bed=self.bed2, allocated_by=self.admin,
        )

    def test_prevent_duplicate_attendance_same_student_and_date(self):
        """Database constraint should block duplicate attendance for same student and date."""
        from datetime import date
        today = date(2026, 10, 4)
        HostelAttendance.objects.create(
            student=self.student1, hostel=self.hostel, room=self.room, date=today, status="PRESENT",
        )

        with transaction.atomic():
            with self.assertRaises(IntegrityError):
                HostelAttendance.objects.create(
                    student=self.student1, hostel=self.hostel, room=self.room, date=today, status="ABSENT",
                )

    def test_warden_mark_attendance_post_view(self):
        """Warden marks attendance via UI, and subsequent update modifies record without error."""
        self.client.login(username="warden_att", password="adminpassword123")
        post_data = {
            "date": "2026-10-04",
            "hostel": self.hostel.id,
            f"status_{self.student1.id}": "PRESENT",
            f"remarks_{self.student1.id}": "On time roll call",
            f"status_{self.student2.id}": "PERMISSION",
            f"remarks_{self.student2.id}": "Library late study pass",
        }
        resp = self.client.post("/hostel/admin/attendance/", post_data)
        self.assertEqual(resp.status_code, 302)

        att1 = HostelAttendance.objects.get(student=self.student1, date="2026-10-04")
        self.assertEqual(att1.status, "PRESENT")
        self.assertEqual(att1.remarks, "On time roll call")

        att2 = HostelAttendance.objects.get(student=self.student2, date="2026-10-04")
        self.assertEqual(att2.status, "PERMISSION")
        self.assertEqual(att2.remarks, "Library late study pass")

        # Re-marking (updating status)
        post_data[f"status_{self.student2.id}"] = "PRESENT"
        post_data[f"remarks_{self.student2.id}"] = "Returned before 10 PM"
        resp2 = self.client.post("/hostel/admin/attendance/", post_data)
        self.assertEqual(resp2.status_code, 302)

        att2.refresh_from_db()
        self.assertEqual(att2.status, "PRESENT")
        self.assertEqual(att2.remarks, "Returned before 10 PM")
        self.assertEqual(HostelAttendance.objects.filter(student=self.student2, date="2026-10-04").count(), 1)

    def test_student_views_only_own_attendance(self):
        """Student accessing /hostel/attendance/ sees only their records."""
        from datetime import date
        HostelAttendance.objects.create(
            student=self.student1, hostel=self.hostel, room=self.room, date=date(2026, 10, 4), status="PRESENT", remarks="Personal remark for student 1",
        )
        HostelAttendance.objects.create(
            student=self.student2, hostel=self.hostel, room=self.room, date=date(2026, 10, 4), status="ABSENT", remarks="Secret remark for student 2",
        )

        self.client.login(username="res1", password="pass123")
        resp = self.client.get("/hostel/attendance/")
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Personal remark for student 1")
        self.assertNotContains(resp, "Secret remark for student 2")


class HostelComplaintWorkflowTests(TestCase):
    def setUp(self):
        from students.models import Department, Course, Student
        self.admin = User.objects.create_superuser(
            username="complaint_warden",
            password="adminpassword123",
            email="warden_comp@smartcollege.edu",
        )
        self.staff_user = User.objects.create_user(
            username="electrician_mike",
            password="password123",
            email="mike@smartcollege.edu",
        )

        self.dept = Department.objects.create(name="School of Engineering")
        self.course = Course.objects.create(name="B.Tech EE", department=self.dept)

        # Student 1
        self.u1 = User.objects.create_user(username="resident_a", password="pass123", email="res_a@college.edu")
        self.student1 = Student.objects.create(
            user=self.u1, name="Karan Joshi", roll_no="EE2026-01",
            department=self.dept, course=self.course, year=2, is_active=True,
        )

        # Student 2
        self.u2 = User.objects.create_user(username="resident_b", password="pass123", email="res_b@college.edu")
        self.student2 = Student.objects.create(
            user=self.u2, name="Sneha Patel", roll_no="EE2026-02",
            department=self.dept, course=self.course, year=2, is_active=True,
        )

        self.hostel = Hostel.objects.create(
            name="Aryabhata Hostel", code="ARB-H", hostel_type="BOYS", address="Campus East",
        )
        self.block = HostelBlock.objects.create(hostel=self.hostel, name="Block B", code="BB")
        self.floor = HostelFloor.objects.create(block=self.block, name="2nd Floor", floor_number=2)
        self.room = HostelRoom.objects.create(
            hostel=self.hostel, block=self.block, floor=self.floor, room_number="204", capacity=2,
        )
        self.bed = HostelBed.objects.create(room=self.room, bed_number="B1")

        self.alloc = HostelAllocation.objects.create(
            student=self.student1, hostel=self.hostel, block=self.block, floor=self.floor,
            room=self.room, bed=self.bed, allocated_by=self.admin,
        )

    def test_full_complaint_lifecycle(self):
        """Student -> Complaint -> Assign -> Resolve -> Student sees resolution."""
        # 1. Student creates complaint
        self.client.login(username="resident_a", password="pass123")
        post_data = {
            "category": "ELECTRICAL",
            "title": "Ceiling fan making clicking noise",
            "description": "The fan in room 204 clicks loudly at speeds 3 and 4.",
            "priority": "HIGH",
        }
        resp = self.client.post("/hostel/complaints/create/", post_data)
        self.assertEqual(resp.status_code, 302)

        complaint = HostelComplaint.objects.filter(student=self.student1).first()
        self.assertIsNotNone(complaint)
        self.assertTrue(complaint.complaint_id.startswith("HOSTEL-CMP-2026-"))
        self.assertEqual(complaint.status, "OPEN")
        self.assertEqual(complaint.hostel, self.hostel)
        self.assertEqual(complaint.room, self.room)

        # 2. Warden assigns maintenance staff & marks IN_PROGRESS
        self.client.login(username="complaint_warden", password="adminpassword123")
        update_data = {
            "status": "IN_PROGRESS",
            "priority": "HIGH",
            "assigned_staff": self.staff_user.id,
            "resolution": "",
        }
        resp = self.client.post(f"/hostel/admin/complaints/{complaint.pk}/", update_data)
        self.assertEqual(resp.status_code, 302)
        complaint.refresh_from_db()
        self.assertEqual(complaint.status, "IN_PROGRESS")
        self.assertEqual(complaint.assigned_staff, self.staff_user)

        # 3. Warden tries to resolve without resolution text -> validation fails
        fail_data = {
            "status": "RESOLVED",
            "priority": "HIGH",
            "assigned_staff": self.staff_user.id,
            "resolution": "",
        }
        resp_fail = self.client.post(f"/hostel/admin/complaints/{complaint.pk}/", fail_data)
        self.assertEqual(resp_fail.status_code, 200)
        self.assertFormError(resp_fail.context["form"], "resolution", "A resolution summary or explanation is required when resolving, closing, or rejecting a complaint.")

        # 4. Warden resolves with detailed resolution notes
        resolve_data = {
            "status": "RESOLVED",
            "priority": "HIGH",
            "assigned_staff": self.staff_user.id,
            "resolution": "Electrician Mike replaced the motor ball bearings and balanced blades. Noise eliminated.",
        }
        resp_ok = self.client.post(f"/hostel/admin/complaints/{complaint.pk}/", resolve_data)
        self.assertEqual(resp_ok.status_code, 302)
        complaint.refresh_from_db()
        self.assertEqual(complaint.status, "RESOLVED")
        self.assertEqual(complaint.resolved_by, self.admin)
        self.assertIsNotNone(complaint.resolved_date)

        # 5. Student views resolution
        self.client.login(username="resident_a", password="pass123")
        resp_student = self.client.get(f"/hostel/complaints/{complaint.pk}/")
        self.assertEqual(resp_student.status_code, 200)
        self.assertContains(resp_student, "Electrician Mike replaced the motor ball bearings")
        self.assertContains(resp_student, "Resolved")

        # 6. Unrelated student tries to view -> 403 Forbidden
        self.client.login(username="resident_b", password="pass123")
        resp_forbidden = self.client.get(f"/hostel/complaints/{complaint.pk}/")
        self.assertEqual(resp_forbidden.status_code, 403)


class HostelWardenAndNoticeTests(TestCase):
    def setUp(self):
        from students.models import Department, Course, Student
        self.dept = Department.objects.create(name="School of Humanities")
        self.course = Course.objects.create(name="BA English", department=self.dept)

        # Super admin
        self.admin = User.objects.create_superuser(
            username="super_hostel_admin",
            password="adminpassword123",
            email="superadmin@smartcollege.edu",
        )

        # Warden A for Hostel A
        self.warden_user_a = User.objects.create_user(
            username="warden_ashok",
            password="wardenpassword123",
            email="ashok@smartcollege.edu",
            is_staff=True,
        )
        self.hostel_a = Hostel.objects.create(
            name="Tagore Bhavan",
            code="TB-A",
            hostel_type="BOYS",
            address="North Campus",
            warden_incharge=self.warden_user_a,
        )
        HostelWarden.objects.create(
            hostel=self.hostel_a,
            user=self.warden_user_a,
            role="WARDEN",
            designation="Hostel Warden",
            contact_number="9876543211",
        )

        # Warden B for Hostel B
        self.warden_user_b = User.objects.create_user(
            username="warden_beena",
            password="wardenpassword123",
            email="beena@smartcollege.edu",
            is_staff=True,
        )
        self.hostel_b = Hostel.objects.create(
            name="Sarojini Bhavan",
            code="SB-B",
            hostel_type="GIRLS",
            address="South Campus",
            warden_incharge=self.warden_user_b,
        )
        HostelWarden.objects.create(
            hostel=self.hostel_b,
            user=self.warden_user_b,
            role="WARDEN",
            designation="Chief Warden",
            contact_number="9876543222",
        )

        # Rooms and Beds for Hostel A
        self.block_a = HostelBlock.objects.create(hostel=self.hostel_a, name="Block 1", code="B1")
        self.floor_a = HostelFloor.objects.create(block=self.block_a, name="Floor 1", floor_number=1)
        self.room_a = HostelRoom.objects.create(hostel=self.hostel_a, block=self.block_a, floor=self.floor_a, room_number="101", capacity=1)
        self.bed_a = HostelBed.objects.create(room=self.room_a, bed_number="1A")

        # Rooms and Beds for Hostel B
        self.block_b = HostelBlock.objects.create(hostel=self.hostel_b, name="Block 2", code="B2")
        self.floor_b = HostelFloor.objects.create(block=self.block_b, name="Floor 2", floor_number=2)
        self.room_b = HostelRoom.objects.create(hostel=self.hostel_b, block=self.block_b, floor=self.floor_b, room_number="202", capacity=1)
        self.bed_b = HostelBed.objects.create(room=self.room_b, bed_number="2B")

        # Student A in Hostel A
        self.u_stud_a = User.objects.create_user(username="student_a", password="pass123", email="stud_a@college.edu")
        self.student_a = Student.objects.create(
            user=self.u_stud_a, name="Anil Sharma", roll_no="HUM2026-01",
            department=self.dept, course=self.course, year=1, is_active=True,
        )
        self.alloc_a = HostelAllocation.objects.create(
            student=self.student_a, hostel=self.hostel_a, block=self.block_a, floor=self.floor_a,
            room=self.room_a, bed=self.bed_a, allocated_by=self.admin,
        )

        # Student B in Hostel B
        self.u_stud_b = User.objects.create_user(username="student_b", password="pass123", email="stud_b@college.edu")
        self.student_b = Student.objects.create(
            user=self.u_stud_b, name="Bhavna Roy", roll_no="HUM2026-02",
            department=self.dept, course=self.course, year=1, is_active=True,
        )
        self.alloc_b = HostelAllocation.objects.create(
            student=self.student_b, hostel=self.hostel_b, block=self.block_b, floor=self.floor_b,
            room=self.room_b, bed=self.bed_b, allocated_by=self.admin,
        )

        # Application for Hostel B
        self.app_b = HostelApplication.objects.create(
            student=self.student_b,
            hostel_preference=self.hostel_b,
            room_type_preference="DOUBLE",
            status="PENDING",
        )

        # Complaint for Hostel B
        self.comp_b = HostelComplaint.objects.create(
            student=self.student_b,
            hostel=self.hostel_b,
            room=self.room_b,
            category="PLUMBING",
            title="Water leakage in 202",
            description="Tap is leaking continuously.",
            status="OPEN",
        )

    def test_warden_scoping_and_cross_hostel_isolation(self):
        """Warden A (Hostel A) cannot view allocations, review applications, take attendance, or view complaints for Hostel B."""
        self.client.login(username="warden_ashok", password="wardenpassword123")

        # 1. Allocations list should only show allocations for Hostel A
        resp_alloc_list = self.client.get("/hostel/admin/allocations/")
        self.assertEqual(resp_alloc_list.status_code, 200)
        self.assertContains(resp_alloc_list, self.alloc_a.allocation_id)
        self.assertNotContains(resp_alloc_list, self.alloc_b.allocation_id)

        # 2. Allocation detail for Hostel B raises 403
        resp_alloc_detail_b = self.client.get(f"/hostel/admin/allocations/{self.alloc_b.pk}/")
        self.assertEqual(resp_alloc_detail_b.status_code, 403)

        # 3. Review application for Hostel B raises 403
        resp_app_review_b = self.client.post(
            f"/hostel/admin/applications/{self.app_b.pk}/review/",
            {"action": "APPROVE", "reviewer_remarks": "Approved by unauthorized warden"},
        )
        self.assertEqual(resp_app_review_b.status_code, 403)

        # 4. Attendance marking for Hostel B raises 403
        resp_att_b = self.client.post(
            "/hostel/admin/attendance/",
            {"hostel": self.hostel_b.id, "date": "2026-10-04"},
        )
        self.assertEqual(resp_att_b.status_code, 403)

        # 5. Complaint detail for Hostel B raises 403
        resp_comp_detail_b = self.client.get(f"/hostel/admin/complaints/{self.comp_b.pk}/")
        self.assertEqual(resp_comp_detail_b.status_code, 403)

    def test_warden_notice_dispatch_and_student_notifications(self):
        """Warden A publishes notice for Hostel A -> active residents of Hostel A receive Notification, Hostel B residents do not."""
        self.client.login(username="warden_ashok", password="wardenpassword123")

        post_data = {
            "hostel": self.hostel_a.id,
            "title": "Annual Fire Drill on Saturday",
            "message": "All residents of Tagore Bhavan must assemble at the courtyard by 10 AM sharp.",
            "priority": "IMPORTANT",
            "publish_date": "2026-10-04",
        }
        resp = self.client.post("/hostel/admin/notices/create/", post_data)
        self.assertEqual(resp.status_code, 302)

        # Verify notice was saved
        notice = HostelNotice.objects.filter(hostel=self.hostel_a, title="Annual Fire Drill on Saturday").first()
        self.assertIsNotNone(notice)
        self.assertEqual(notice.created_by, self.warden_user_a)

        # Verify Notification generated for student_a (Hostel A resident)
        notif_a = Notification.objects.filter(recipient=self.u_stud_a, title__icontains="Hostel Notice").first()
        self.assertIsNotNone(notif_a)
        self.assertIn("Fire Drill", notif_a.title)

        # Verify Notification NOT generated for student_b (Hostel B resident)
        notif_b = Notification.objects.filter(recipient=self.u_stud_b, title__icontains="Hostel Notice").first()
        self.assertIsNone(notif_b)

        # Student A views notice in /hostel/notices/
        self.client.login(username="student_a", password="pass123")
        resp_stud_notices = self.client.get("/hostel/notices/")
        self.assertEqual(resp_stud_notices.status_code, 200)
        self.assertContains(resp_stud_notices, "Annual Fire Drill on Saturday")
        self.assertContains(resp_stud_notices, "Tagore Bhavan")


class HostelStudentPortalTests(TestCase):
    def setUp(self):
        from students.models import Department, Course, Student

        self.dept = Department.objects.create(name="School of Computing")
        self.course = Course.objects.create(name="B.Tech AI & Data Science", department=self.dept)

        # Student A
        self.user_a = User.objects.create_user(username="portal_student_a", password="password123", email="portal_a@college.edu")
        self.student_a = Student.objects.create(
            user=self.user_a,
            name="Aditya Verma",
            roll_no="AI202601",
            department=self.dept,
            course=self.course,
            year=2,
        )

        # Student B
        self.user_b = User.objects.create_user(username="portal_student_b", password="password123", email="portal_b@college.edu")
        self.student_b = Student.objects.create(
            user=self.user_b,
            name="Bhavna Rao",
            roll_no="AI202602",
            department=self.dept,
            course=self.course,
            year=2,
        )

        # Hostel Core Structure
        self.hostel = Hostel.objects.create(
            name="Aryabhata Hall of Residence",
            code="ABH-01",
            hostel_type="BOYS",
            address="Campus North Sector",
            contact_phone="9988776655",
            contact_email="abh@college.edu",
        )
        self.block = HostelBlock.objects.create(hostel=self.hostel, name="Block A", code="A")
        self.floor = HostelFloor.objects.create(block=self.block, name="Ground Floor", floor_number=0)
        self.room = HostelRoom.objects.create(
            hostel=self.hostel,
            block=self.block,
            floor=self.floor,
            room_number="G-05",
            room_type="DOUBLE",
            capacity=2,
            monthly_rent=5000.00,
        )
        self.bed1 = HostelBed.objects.create(room=self.room, bed_number="01", status="AVAILABLE")
        self.bed2 = HostelBed.objects.create(room=self.room, bed_number="02", status="AVAILABLE")

        # Allocation for Student A
        self.alloc_a = HostelAllocation.objects.create(
            allocation_id="HOSTEL-ALLOC-2026-TEST01",
            student=self.student_a,
            hostel=self.hostel,
            block=self.block,
            floor=self.floor,
            room=self.room,
            bed=self.bed1,
            allocation_date="2026-08-01",
            academic_year="2026-2027",
            status="ACTIVE",
        )
        self.bed1.status = "OCCUPIED"
        self.bed1.save()

        # Fees for Student A
        self.fee = FeeRecord.objects.create(
            student=self.student_a,
            fee_type="HOSTEL",
            title="Hostel Admission Fee",
            amount=Decimal("15000.00"),
            academic_year="2026-2027",
        )
        FeePayment.objects.create(
            fee_record=self.fee,
            amount=Decimal("10000.00"),
            payment_mode="UPI",
            receipt_number="HOSTEL-REC-TEST01",
        )

        # Attendance for Student A
        HostelAttendance.objects.create(
            student=self.student_a,
            hostel=self.hostel,
            room=self.room,
            date="2026-10-01",
            status="PRESENT",
        )
        HostelAttendance.objects.create(
            student=self.student_a,
            hostel=self.hostel,
            room=self.room,
            date="2026-10-02",
            status="ABSENT",
        )

        # Complaint for Student A
        self.complaint = HostelComplaint.objects.create(
            student=self.student_a,
            hostel=self.hostel,
            room=self.room,
            category="ELECTRICAL",
            title="Study lamp switch socket broken",
            description="Power socket near study desk sparks when plugged in.",
            priority="HIGH",
            status="OPEN",
        )

        # Notice for Hostel
        self.notice = HostelNotice.objects.create(
            hostel=self.hostel,
            title="Hostel Gate Timings Revision",
            message="Curfew time for Aryabhata Hall is 9:30 PM starting Monday.",
            priority="IMPORTANT",
            publish_date="2026-10-01",
        )

    def test_student_hostel_portal_renders_active_allocation(self):
        """Student A visits /hostel/ and sees complete accommodation metrics."""
        self.client.login(username="portal_student_a", password="password123")
        resp = self.client.get("/hostel/")
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Aryabhata Hall of Residence")
        self.assertContains(resp, "Room G-05")
        self.assertContains(resp, "Bed 01")
        self.assertContains(resp, "HOSTEL-ALLOC-2026-TEST01")
        # Fee metrics
        self.assertContains(resp, "5000")  # Outstanding balance
        self.assertContains(resp, "10000") # Paid amount
        # Attendance metrics
        self.assertContains(resp, "50")    # 1 present out of 2 days = 50.0%
        # Complaint
        self.assertContains(resp, "Study lamp switch socket broken")
        # Notice
        self.assertContains(resp, "Hostel Gate Timings Revision")

    def test_student_hostel_portal_unallocated_student(self):
        """Student B (unallocated) visits /hostel/ and sees unallocated state with application CTA."""
        self.client.login(username="portal_student_b", password="password123")
        resp = self.client.get("/hostel/")
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "No Active Hostel Allocation")
        self.assertContains(resp, "Submit Application")

    def test_student_dashboard_integration(self):
        """Student dashboard at /students/ embeds the complete Hostel Accommodation section."""
        self.client.login(username="portal_student_a", password="password123")
        resp = self.client.get("/students/")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("hostel_summary", resp.context)
        self.assertContains(resp, "Hostel Accommodation &amp; Portal")
        self.assertContains(resp, "Aryabhata Hall of Residence")
        self.assertContains(resp, "Room G-05")
        self.assertContains(resp, "Hostel Fees")
        self.assertContains(resp, "Hostel Attendance")
        self.assertContains(resp, "Complaints")

    def test_student_isolation_in_portal(self):
        """Student B cannot view Student A's private complaint or allocation data."""
        self.client.login(username="portal_student_b", password="password123")
        resp = self.client.get("/hostel/")
        self.assertEqual(resp.status_code, 200)
        self.assertNotContains(resp, "HOSTEL-ALLOC-2026-TEST01")
        self.assertNotContains(resp, "Study lamp switch socket broken")


class HostelAdminDashboardTests(TestCase):
    def setUp(self):
        from students.models import Department, Course, Student

        self.admin = User.objects.create_superuser(
            username="hostel_dash_admin",
            password="adminpassword123",
            email="dash_admin@smartcollege.edu",
        )
        self.warden_user = User.objects.create_user(
            username="dash_warden",
            password="wardenpassword123",
            email="dash_warden@college.edu",
        )
        self.student_user = User.objects.create_user(
            username="dash_student",
            password="studentpassword123",
            email="dash_student@college.edu",
        )

        self.dept = Department.objects.create(name="School of Science")
        self.course = Course.objects.create(name="B.Sc Physics", department=self.dept)
        self.student = Student.objects.create(
            user=self.student_user,
            name="Rohit Verma",
            roll_no="SCI202601",
            department=self.dept,
            course=self.course,
            year=1,
        )

        # Hostel 1 (Warden assigned)
        self.hostel1 = Hostel.objects.create(
            name="Kalam Hall",
            code="KLM-01",
            hostel_type="BOYS",
            address="Zone A",
            contact_phone="1234567890",
            warden_incharge=self.warden_user,
        )
        self.block1 = HostelBlock.objects.create(hostel=self.hostel1, name="B-1", code="B1")
        self.floor1 = HostelFloor.objects.create(block=self.block1, name="F-1", floor_number=1)
        self.room1 = HostelRoom.objects.create(
            hostel=self.hostel1,
            block=self.block1,
            floor=self.floor1,
            room_number="101",
            room_type="SINGLE",
            capacity=1,
            monthly_rent=4000.00,
        )
        self.bed1 = HostelBed.objects.create(room=self.room1, bed_number="01", status="AVAILABLE")

        # Hostel 2 (Not assigned to warden)
        self.hostel2 = Hostel.objects.create(
            name="Sarabhai Hall",
            code="SRB-02",
            hostel_type="BOYS",
            address="Zone B",
            contact_phone="0987654321",
        )
        self.block2 = HostelBlock.objects.create(hostel=self.hostel2, name="B-2", code="B2")
        self.floor2 = HostelFloor.objects.create(block=self.block2, name="F-1", floor_number=1)
        self.room2 = HostelRoom.objects.create(
            hostel=self.hostel2,
            block=self.block2,
            floor=self.floor2,
            room_number="201",
            room_type="DOUBLE",
            capacity=2,
            monthly_rent=3500.00,
        )
        self.bed2 = HostelBed.objects.create(room=self.room2, bed_number="01", status="AVAILABLE")
        self.bed3 = HostelBed.objects.create(room=self.room2, bed_number="02", status="AVAILABLE")

        # Allocation in Hostel 1
        self.alloc = HostelAllocation.objects.create(
            allocation_id="HOSTEL-ALLOC-2026-DASH01",
            student=self.student,
            hostel=self.hostel1,
            block=self.block1,
            floor=self.floor1,
            room=self.room1,
            bed=self.bed1,
            allocation_date="2026-09-01",
            academic_year="2026-2027",
            status="ACTIVE",
        )
        self.bed1.status = "OCCUPIED"
        self.bed1.save()

        # Application
        self.app = HostelApplication.objects.create(
            application_id="HOSTEL-APP-2026-DASH01",
            student=self.student,
            hostel_preference=self.hostel1,
            room_type_preference="SINGLE",
            academic_year="2026-2027",
            reason="Long commute",
            status="PENDING",
        )

        # Complaint
        self.complaint = HostelComplaint.objects.create(
            student=self.student,
            hostel=self.hostel1,
            room=self.room1,
            category="PLUMBING",
            title="Leaking tap",
            description="Tap drips constantly.",
            priority="MEDIUM",
            status="OPEN",
        )

        # Attendance
        HostelAttendance.objects.create(
            student=self.student,
            hostel=self.hostel1,
            room=self.room1,
            date="2026-10-01",
            status="PRESENT",
        )

    def test_admin_dashboard_full_view(self):
        """Admin views /hostel/dashboard/ and sees all 10 KPI metrics and charts."""
        self.client.login(username="hostel_dash_admin", password="adminpassword123")
        resp = self.client.get("/hostel/dashboard/")
        self.assertEqual(resp.status_code, 200)

        # Check 10 KPIs in context
        kpi = resp.context["kpi"]
        self.assertEqual(kpi["total_hostels"], 2)
        self.assertEqual(kpi["total_rooms"], 2)
        self.assertEqual(kpi["total_beds"], 3)
        self.assertEqual(kpi["occupied_beds"], 1)
        self.assertEqual(kpi["available_beds"], 2)
        self.assertAlmostEqual(kpi["occupancy_rate"], 33.3, places=1)
        self.assertEqual(kpi["pending_applications"], 1)
        self.assertEqual(kpi["active_residents"], 1)
        self.assertEqual(kpi["open_complaints"], 1)
        self.assertIn("outstanding_fees", kpi)

        # Check charts in context
        self.assertIn("chart_hostel_occupancy", resp.context)
        self.assertIn("chart_room_availability", resp.context)
        self.assertIn("chart_application_status", resp.context)
        self.assertIn("chart_complaint_status", resp.context)
        self.assertIn("chart_attendance", resp.context)

        # Check rendered HTML
        self.assertContains(resp, "Hostel Operations &amp; Capacity Dashboard")
        self.assertContains(resp, "Kalam Hall")
        self.assertContains(resp, "Sarabhai Hall")
        self.assertContains(resp, "chartHostelOccupancy")
        self.assertContains(resp, "chartRoomAvailability")

    def test_warden_scoping_on_dashboard(self):
        """Warden views /hostel/dashboard/ and is scoped strictly to Kalam Hall."""
        self.client.login(username="dash_warden", password="wardenpassword123")
        resp = self.client.get("/hostel/dashboard/")
        self.assertEqual(resp.status_code, 200)

        kpi = resp.context["kpi"]
        self.assertEqual(kpi["total_hostels"], 1) # Only Kalam Hall
        self.assertEqual(kpi["total_rooms"], 1)
        self.assertEqual(kpi["total_beds"], 1)
        self.assertEqual(kpi["occupied_beds"], 1)
        self.assertEqual(kpi["available_beds"], 0)
        self.assertEqual(kpi["occupancy_rate"], 100.0)

        self.assertContains(resp, "Kalam Hall")
        self.assertNotContains(resp, "Sarabhai Hall")

    def test_student_restricted_from_admin_dashboard(self):
        """Student cannot access /hostel/dashboard/ and is redirected."""
        self.client.login(username="dash_student", password="studentpassword123")
        resp = self.client.get("/hostel/dashboard/")
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp.url, "/hostel/")


class HostelRoomSearchTests(TestCase):
    def setUp(self):
        from students.models import Department, Course, Student

        self.admin = User.objects.create_superuser(
            username="hostel_search_admin",
            password="adminpassword123",
            email="search_admin@smartcollege.edu",
        )
        self.warden_user = User.objects.create_user(
            username="search_warden",
            password="wardenpassword123",
            email="search_warden@college.edu",
        )
        self.student_user = User.objects.create_user(
            username="search_student",
            password="studentpassword123",
            email="search_student@college.edu",
        )

        self.dept = Department.objects.create(name="School of Humanities")
        self.course = Course.objects.create(name="B.A English", department=self.dept)
        self.student = Student.objects.create(
            user=self.student_user,
            name="Sneha Sen",
            roll_no="HUM202601",
            department=self.dept,
            course=self.course,
            year=1,
        )

        # Hostel 1 (Assigned to warden)
        self.hostel1 = Hostel.objects.create(
            name="Gargi Girls Hostel",
            code="GGH-01",
            hostel_type="GIRLS",
            warden_incharge=self.warden_user,
        )
        self.block1 = HostelBlock.objects.create(hostel=self.hostel1, name="Wing A", code="WA")
        self.floor1 = HostelFloor.objects.create(block=self.block1, name="Floor 1", floor_number=1)

        # Room 101: Single, 1 available bed
        self.room1 = HostelRoom.objects.create(
            hostel=self.hostel1,
            block=self.block1,
            floor=self.floor1,
            room_number="101",
            room_type="SINGLE",
            capacity=1,
            status="AVAILABLE",
        )
        self.bed1 = HostelBed.objects.create(room=self.room1, bed_number="01", status="AVAILABLE")

        # Room 102: Double, 1 occupied, 1 available
        self.room2 = HostelRoom.objects.create(
            hostel=self.hostel1,
            block=self.block1,
            floor=self.floor1,
            room_number="102",
            room_type="DOUBLE",
            capacity=2,
            status="PARTIALLY_OCCUPIED",
        )
        self.bed2 = HostelBed.objects.create(room=self.room2, bed_number="01", status="OCCUPIED")
        self.bed3 = HostelBed.objects.create(room=self.room2, bed_number="02", status="AVAILABLE")

        # Room 103: Triple, 3 occupied (FULL)
        self.room3 = HostelRoom.objects.create(
            hostel=self.hostel1,
            block=self.block1,
            floor=self.floor1,
            room_number="103",
            room_type="TRIPLE",
            capacity=3,
            status="FULL",
        )
        self.bed4 = HostelBed.objects.create(room=self.room3, bed_number="01", status="OCCUPIED")
        self.bed5 = HostelBed.objects.create(room=self.room3, bed_number="02", status="OCCUPIED")
        self.bed6 = HostelBed.objects.create(room=self.room3, bed_number="03", status="OCCUPIED")

        # Hostel 2 (Not assigned to warden)
        self.hostel2 = Hostel.objects.create(
            name="Maitreyi Girls Hostel",
            code="MGH-02",
            hostel_type="GIRLS",
        )
        self.block2 = HostelBlock.objects.create(hostel=self.hostel2, name="Wing B", code="WB")
        self.floor2 = HostelFloor.objects.create(block=self.block2, name="Floor 1", floor_number=1)
        self.room4 = HostelRoom.objects.create(
            hostel=self.hostel2,
            block=self.block2,
            floor=self.floor2,
            room_number="201",
            room_type="DOUBLE",
            capacity=2,
            status="AVAILABLE",
        )
        self.bed7 = HostelBed.objects.create(room=self.room4, bed_number="01", status="AVAILABLE")
        self.bed8 = HostelBed.objects.create(room=self.room4, bed_number="02", status="AVAILABLE")

    def test_room_search_all_and_counts(self):
        """Admin views /hostel/rooms/ without filters, sees all rooms and accurate bed counts."""
        self.client.login(username="hostel_search_admin", password="adminpassword123")
        resp = self.client.get("/hostel/rooms/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.context["total_rooms_count"], 4)
        self.assertEqual(resp.context["total_avail_beds_count"], 4)
        self.assertEqual(resp.context["total_occ_beds_count"], 4)
        self.assertContains(resp, "Gargi Girls Hostel")
        self.assertContains(resp, "Maitreyi Girls Hostel")

    def test_room_search_min_available_beds_filter(self):
        """Filtering by min_available=2 only returns rooms with at least 2 vacant beds (room4)."""
        self.client.login(username="hostel_search_admin", password="adminpassword123")
        resp = self.client.get("/hostel/rooms/?min_available=2")
        self.assertEqual(resp.status_code, 200)
        rooms = list(resp.context["rooms"])
        self.assertEqual(len(rooms), 1)
        self.assertEqual(rooms[0].room_number, "201")
        self.assertContains(resp, "Room 201")
        self.assertNotContains(resp, "Room 101")
        self.assertNotContains(resp, "Room 102")
        self.assertNotContains(resp, "Room 103")

    def test_room_search_type_and_status_filter(self):
        """Filtering by room_type=SINGLE and status=AVAILABLE returns only Room 101."""
        self.client.login(username="hostel_search_admin", password="adminpassword123")
        resp = self.client.get("/hostel/rooms/?room_type=SINGLE&status=AVAILABLE")
        self.assertEqual(resp.status_code, 200)
        rooms = list(resp.context["rooms"])
        self.assertEqual(len(rooms), 1)
        self.assertEqual(rooms[0].room_number, "101")

    def test_allocatable_beds_only_shown(self):
        """Room 102 (Double, 1 occupied, 1 available) only displays Bed 02 under Allocatable Beds."""
        self.client.login(username="hostel_search_admin", password="adminpassword123")
        resp = self.client.get("/hostel/rooms/?q=102")
        self.assertEqual(resp.status_code, 200)
        rooms = list(resp.context["rooms"])
        self.assertEqual(len(rooms), 1)
        room_obj = rooms[0]
        self.assertEqual(len(room_obj.allocatable_beds), 1)
        self.assertEqual(room_obj.allocatable_beds[0].bed_number, "02")
        self.assertContains(resp, "Bed 02")

    def test_warden_scoping_room_search(self):
        """Warden is strictly scoped to Gargi Girls Hostel and cannot view Maitreyi Girls Hostel."""
        self.client.login(username="search_warden", password="wardenpassword123")
        resp = self.client.get("/hostel/rooms/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.context["total_rooms_count"], 3)
        self.assertContains(resp, "Gargi Girls Hostel")
        self.assertNotContains(resp, "Maitreyi Girls Hostel")

    def test_student_restricted_from_room_search(self):
        """Student cannot access /hostel/rooms/."""
        self.client.login(username="search_student", password="studentpassword123")
        resp = self.client.get("/hostel/rooms/")
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp.url, "/hostel/")


class HostelVisitorTests(TestCase):
    def setUp(self):
        from students.models import Student
        from django.utils import timezone
        import datetime

        self.admin = User.objects.create_superuser(
            username="visitor_admin",
            password="adminpassword123",
            email="visitor_admin@smartcollege.edu",
        )

        self.warden1_user = User.objects.create_user(
            username="warden_one",
            password="wardenpassword123",
            first_name="Warden",
            last_name="One",
        )
        self.warden2_user = User.objects.create_user(
            username="warden_two",
            password="wardenpassword123",
            first_name="Warden",
            last_name="Two",
        )

        self.hostel1 = Hostel.objects.create(
            name="Tagore Boys Hostel",
            code="TBH",
            hostel_type="BOYS",
            address="North Campus",
            contact_phone="9988776655",
            contact_email="tagore@smartcollege.edu",
        )
        self.hostel2 = Hostel.objects.create(
            name="Sarojini Girls Hostel",
            code="SGH",
            hostel_type="GIRLS",
            address="South Campus",
            contact_phone="9988776644",
            contact_email="sarojini@smartcollege.edu",
        )

        HostelWarden.objects.create(user=self.warden1_user, hostel=self.hostel1, is_active=True)
        HostelWarden.objects.create(user=self.warden2_user, hostel=self.hostel2, is_active=True)

        self.block1 = HostelBlock.objects.create(hostel=self.hostel1, name="Block A", code="A")
        self.floor1 = HostelFloor.objects.create(block=self.block1, floor_number=1, name="First Floor")
        self.room1 = HostelRoom.objects.create(
            hostel=self.hostel1, block=self.block1, floor=self.floor1,
            room_number="101", room_type="SINGLE", capacity=1, status="OCCUPIED",
        )
        self.bed1 = HostelBed.objects.create(room=self.room1, bed_number="01", status="OCCUPIED")

        self.block2 = HostelBlock.objects.create(hostel=self.hostel2, name="Block B", code="B")
        self.floor2 = HostelFloor.objects.create(block=self.block2, floor_number=1, name="First Floor")
        self.room2 = HostelRoom.objects.create(
            hostel=self.hostel2, block=self.block2, floor=self.floor2,
            room_number="201", room_type="SINGLE", capacity=1, status="OCCUPIED",
        )
        self.bed2 = HostelBed.objects.create(room=self.room2, bed_number="01", status="OCCUPIED")

        # Department and Students
        from students.models import Department
        self.dept = Department.objects.create(name="Computer Science")

        self.student1_user = User.objects.create_user(
            username="student_res1", password="studentpassword123", first_name="Aarav", last_name="Sharma"
        )
        self.student1 = Student.objects.create(
            user=self.student1_user,
            name="Aarav Sharma",
            roll_no="VIS-01",
            department=self.dept,
            year=1,
            email="aarav@smartcollege.edu",
            is_active=True,
        )

        self.student2_user = User.objects.create_user(
            username="student_res2", password="studentpassword123", first_name="Ananya", last_name="Iyer"
        )
        self.student2 = Student.objects.create(
            user=self.student2_user,
            name="Ananya Iyer",
            roll_no="VIS-02",
            department=self.dept,
            year=1,
            email="ananya@smartcollege.edu",
            is_active=True,
        )

        self.student_nonres_user = User.objects.create_user(
            username="student_nonres", password="studentpassword123", first_name="Non", last_name="Resident"
        )
        self.student_nonres = Student.objects.create(
            user=self.student_nonres_user,
            name="Non Resident",
            roll_no="VIS-03",
            department=self.dept,
            year=1,
            email="nonres@smartcollege.edu",
            is_active=True,
        )

        # Allocations
        self.alloc1 = HostelAllocation.objects.create(
            student=self.student1,
            hostel=self.hostel1,
            block=self.block1,
            floor=self.floor1,
            room=self.room1,
            bed=self.bed1,
            status="ACTIVE",
            academic_year="2026-27",
            allocation_date=timezone.now().date(),
        )
        self.alloc2 = HostelAllocation.objects.create(
            student=self.student2,
            hostel=self.hostel2,
            block=self.block2,
            floor=self.floor2,
            room=self.room2,
            bed=self.bed2,
            status="ACTIVE",
            academic_year="2026-27",
            allocation_date=timezone.now().date(),
        )

        # Pre-existing visitor passes
        self.visitor1 = HostelVisitor.objects.create(
            student=self.student1,
            hostel=self.hostel1,
            visitor_name="Rajesh Sharma",
            relationship="Father",
            phone="9876543210",
            visit_date=timezone.now().date(),
            purpose="Monthly family visit",
            status="PENDING",
        )
        self.visitor2 = HostelVisitor.objects.create(
            student=self.student2,
            hostel=self.hostel2,
            visitor_name="Meenakshi Iyer",
            relationship="Mother",
            phone="9876543222",
            visit_date=timezone.now().date(),
            purpose="Delivering study materials",
            status="APPROVED",
        )

    def test_student_can_request_visitor_pass(self):
        """Resident student can successfully submit a visitor pass request."""
        self.client.login(username="student_res1", password="studentpassword123")
        post_data = {
            "visitor_name": "Vikram Sharma",
            "relationship": "Brother",
            "phone": "9876501234",
            "visit_date": "2026-10-20",
            "purpose": "Weekend visit",
            "remarks": "Arriving by train around noon",
        }
        resp = self.client.post("/hostel/visitors/create/", post_data)
        self.assertRedirects(resp, "/hostel/visitors/")

        new_vis = HostelVisitor.objects.filter(visitor_name="Vikram Sharma").first()
        self.assertIsNotNone(new_vis)
        self.assertEqual(new_vis.student, self.student1)
        self.assertEqual(new_vis.hostel, self.hostel1)
        self.assertEqual(new_vis.status, "PENDING")

    def test_non_resident_student_cannot_request_visitor(self):
        """Student without active hostel allocation cannot request a visitor pass."""
        self.client.login(username="student_nonres", password="studentpassword123")
        resp = self.client.get("/hostel/visitors/create/")
        self.assertRedirects(resp, "/hostel/visitors/")

        post_data = {
            "visitor_name": "Test Visitor",
            "relationship": "Friend",
            "phone": "9876500000",
            "visit_date": "2026-10-20",
            "purpose": "Testing",
        }
        post_resp = self.client.post("/hostel/visitors/create/", post_data)
        self.assertRedirects(post_resp, "/hostel/visitors/")
        self.assertFalse(HostelVisitor.objects.filter(visitor_name="Test Visitor").exists())

    def test_student_can_view_only_own_visitors(self):
        """Student sees only visitor passes associated with their own student profile."""
        self.client.login(username="student_res1", password="studentpassword123")
        resp = self.client.get("/hostel/visitors/")
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Rajesh Sharma")
        self.assertNotContains(resp, "Meenakshi Iyer")

    def test_warden_scoping_for_visitor_registry(self):
        """Warden of Hostel 1 sees only visitors for Hostel 1 in the admin roster."""
        self.client.login(username="warden_one", password="wardenpassword123")
        resp = self.client.get("/hostel/admin/visitors/")
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Rajesh Sharma")
        self.assertNotContains(resp, "Meenakshi Iyer")

    def test_warden_cannot_update_other_hostel_visitor(self):
        """Warden of Hostel 1 cannot view or modify visitor pass for Hostel 2."""
        self.client.login(username="warden_one", password="wardenpassword123")
        resp = self.client.get(f"/hostel/admin/visitors/{self.visitor2.pk}/")
        self.assertEqual(resp.status_code, 403)

    def test_warden_can_update_visitor_and_gate_pass(self):
        """Warden can update visitor status, record gate timings, and trigger notifications."""
        self.client.login(username="warden_one", password="wardenpassword123")
        post_data = {
            "status": "CHECKED_IN",
            "entry_time": "10:30",
            "exit_time": "",
            "remarks": "ID card verified at entrance gate.",
        }
        resp = self.client.post(f"/hostel/admin/visitors/{self.visitor1.pk}/", post_data)
        self.assertRedirects(resp, "/hostel/admin/visitors/")

        self.visitor1.refresh_from_db()
        self.assertEqual(self.visitor1.status, "CHECKED_IN")
        self.assertEqual(self.visitor1.approved_by, self.warden1_user)
        self.assertIn("ID card verified", self.visitor1.remarks)

        # Check notification was created for student 1
        notif = Notification.objects.filter(recipient=self.student1_user).last()
        self.assertIsNotNone(notif)
        self.assertIn("Visitor Pass Update", notif.title)


class HostelReportsAndExportsTests(TestCase):
    def setUp(self):
        from students.models import Department, Student
        self.admin_user = User.objects.create_superuser(
            username="reports_admin",
            password="adminpassword123",
            email="reportsadmin@smartcollege.edu",
        )
        self.warden_user = User.objects.create_user(
            username="reports_warden",
            password="wardenpassword123",
            email="warden_rep@smartcollege.edu",
        )
        self.student_user = User.objects.create_user(
            username="reports_student",
            password="studentpassword123",
            email="stud_rep@smartcollege.edu",
        )

        self.dept, _ = Department.objects.get_or_create(name="Computer Science")
        self.student = Student.objects.create(
            user=self.student_user,
            name="Rahul Reports",
            roll_no="REP-101",
            department=self.dept,
            year=2,
            email="rahul.reports@smartcollege.edu",
            is_active=True,
        )

        self.hostel1 = Hostel.objects.create(
            name="Alpha Boys Hostel",
            code="ALPHA-BH",
            hostel_type="BOYS",
            is_active=True,
        )
        self.hostel2 = Hostel.objects.create(
            name="Beta Girls Hostel",
            code="BETA-GH",
            hostel_type="GIRLS",
            is_active=True,
        )

        HostelWarden.objects.create(
            user=self.warden_user,
            hostel=self.hostel1,
            role="ASSISTANT_WARDEN",
            is_active=True,
        )

        self.block1 = HostelBlock.objects.create(hostel=self.hostel1, name="Block A", code="A")
        self.floor1 = HostelFloor.objects.create(block=self.block1, name="1st Floor", floor_number=1)
        self.room1 = HostelRoom.objects.create(
            hostel=self.hostel1,
            block=self.block1,
            floor=self.floor1,
            room_number="101",
            capacity=2,
            monthly_rent=5000,
        )
        self.bed1 = HostelBed.objects.create(room=self.room1, bed_number="B1", status="OCCUPIED")
        self.bed2 = HostelBed.objects.create(room=self.room1, bed_number="B2", status="AVAILABLE")

        self.block2 = HostelBlock.objects.create(hostel=self.hostel2, name="Block B", code="B")
        self.floor2 = HostelFloor.objects.create(block=self.block2, name="1st Floor", floor_number=1)
        self.room2 = HostelRoom.objects.create(
            hostel=self.hostel2,
            block=self.block2,
            floor=self.floor2,
            room_number="201",
            capacity=2,
            monthly_rent=5000,
        )
        self.bed3 = HostelBed.objects.create(room=self.room2, bed_number="B1", status="AVAILABLE")

        # Allocation
        self.alloc = HostelAllocation.objects.create(
            student=self.student,
            hostel=self.hostel1,
            block=self.block1,
            floor=self.floor1,
            room=self.room1,
            bed=self.bed1,
            status="ACTIVE",
            academic_year="2026-27",
            allocation_date=timezone.now().date(),
        )

        # Application
        self.app = HostelApplication.objects.create(
            student=self.student,
            hostel_preference=self.hostel1,
            room_type_preference="DOUBLE",
            academic_year="2026-27",
            status="APPROVED",
            reviewed_by=self.warden_user,
            reviewed_date=timezone.now(),
        )

        # Lifecycle CheckInOut
        self.checkin = HostelCheckInOut.objects.create(
            allocation=self.alloc,
            student=self.student,
            event_type="CHECK_IN",
            event_date=timezone.now().date(),
            processed_by=self.warden_user,
        )

        # Attendance
        self.attendance = HostelAttendance.objects.create(
            hostel=self.hostel1,
            student=self.student,
            date=timezone.now().date(),
            status="PRESENT",
            marked_by=self.warden_user,
        )

        # Complaint
        self.complaint = HostelComplaint.objects.create(
            student=self.student,
            hostel=self.hostel1,
            room=self.room1,
            title="Fan regulator faulty",
            description="Fan speed controller broken and sparking",
            category="ELECTRICAL",
            priority="HIGH",
            status="IN_PROGRESS",
        )

        # Room transfer
        self.transfer = HostelRoomTransfer.objects.create(
            student=self.student,
            allocation=self.alloc,
            old_hostel=self.hostel1,
            old_block=self.block1,
            old_floor=self.floor1,
            old_room=self.room1,
            old_bed=self.bed1,
            new_hostel=self.hostel1,
            new_block=self.block1,
            new_floor=self.floor1,
            new_room=self.room1,
            new_bed=self.bed2,
            reason="Noise issues near entrance",
            approved_by=self.warden_user,
        )

        # Visitor
        self.visitor = HostelVisitor.objects.create(
            student=self.student,
            hostel=self.hostel1,
            visitor_name="Suresh Reports",
            relationship="Father",
            phone="9876543210",
            visit_date=timezone.now().date(),
            purpose="Weekend visit",
            status="APPROVED",
        )

    def test_admin_can_access_reports_hub(self):
        """Admin user can access the central reports hub."""
        self.client.login(username="reports_admin", password="adminpassword123")
        resp = self.client.get("/hostel/admin/reports/")
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Hostel Audit Reports")
        self.assertContains(resp, "Hostel Occupancy &amp; Capacity")
        self.assertContains(resp, "Resident Allocation Roster")
        self.assertContains(resp, "Hostel Admission &amp; Application Log")
        self.assertContains(resp, "Check-in &amp; Check-out History")
        self.assertContains(resp, "Room &amp; Bed Transfer Audit Trail")

    def test_student_forbidden_from_reports_hub(self):
        """Regular student cannot access the hostel reports hub."""
        self.client.login(username="reports_student", password="studentpassword123")
        resp = self.client.get("/hostel/admin/reports/")
        self.assertEqual(resp.status_code, 403)

    def test_all_excel_exports_return_200_and_spreadsheet(self):
        """Verify all 10 Excel reports export valid .xlsx files with correct headers."""
        self.client.login(username="reports_admin", password="adminpassword123")
        excel_endpoints = [
            "/hostel/admin/reports/occupancy/excel/",
            "/hostel/admin/reports/allocations/excel/",
            "/hostel/admin/reports/availability/excel/",
            "/hostel/admin/reports/attendance/excel/",
            "/hostel/admin/reports/fees/excel/",
            "/hostel/admin/reports/complaints/excel/",
            "/hostel/admin/reports/applications/excel/",
            "/hostel/admin/reports/checkinout/excel/",
            "/hostel/admin/reports/transfers/excel/",
            "/hostel/admin/reports/visitors/excel/",
        ]
        for url in excel_endpoints:
            resp = self.client.get(url)
            self.assertEqual(resp.status_code, 200, f"Endpoint {url} failed with {resp.status_code}")
            self.assertEqual(
                resp["Content-Type"],
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                f"Wrong content type for {url}",
            )
            self.assertTrue(len(resp.content) > 500, f"File content too small for {url}")

    def test_all_pdf_exports_return_200_and_pdf(self):
        """Verify all 10 PDF reports export valid printable documents."""
        self.client.login(username="reports_admin", password="adminpassword123")
        pdf_endpoints = [
            "/hostel/admin/reports/occupancy/pdf/",
            "/hostel/admin/reports/allocations/pdf/",
            "/hostel/admin/reports/availability/pdf/",
            "/hostel/admin/reports/attendance/pdf/",
            "/hostel/admin/reports/fees/pdf/",
            "/hostel/admin/reports/complaints/pdf/",
            "/hostel/admin/reports/applications/pdf/",
            "/hostel/admin/reports/checkinout/pdf/",
            "/hostel/admin/reports/transfers/pdf/",
            "/hostel/admin/reports/visitors/pdf/",
        ]
        for url in pdf_endpoints:
            resp = self.client.get(url)
            self.assertEqual(resp.status_code, 200, f"PDF Endpoint {url} failed with {resp.status_code}")
            self.assertEqual(resp["Content-Type"], "application/pdf", f"Wrong content type for {url}")
            self.assertTrue(resp.content.startswith(b"%PDF"), f"Response for {url} is not a valid PDF")

    def test_warden_scoping_in_reports(self):
        """Warden can export reports for their assigned hostel only."""
        self.client.login(username="reports_warden", password="wardenpassword123")
        resp = self.client.get("/hostel/admin/reports/occupancy/excel/")
        self.assertEqual(resp.status_code, 200)

        # Filtering by their own hostel works
        resp = self.client.get(f"/hostel/admin/reports/occupancy/excel/?hostel={self.hostel1.id}")
        self.assertEqual(resp.status_code, 200)


class HostelNotificationIntegrationTests(TestCase):
    def setUp(self):
        from students.models import Department, Student
        self.admin = User.objects.create_superuser(
            username="notif_admin", password="adminpassword123", email="nadmin@smartcollege.edu"
        )
        self.warden = User.objects.create_user(
            username="notif_warden", password="wardenpassword123", email="nwarden@smartcollege.edu"
        )
        self.student_user = User.objects.create_user(
            username="notif_student", password="studentpassword123", email="nstudent@smartcollege.edu"
        )
        self.dept, _ = Department.objects.get_or_create(name="Notification Dept")
        self.student = Student.objects.create(
            user=self.student_user,
            name="Aarav Notif",
            roll_no="NOTIF-01",
            department=self.dept,
            year=1,
            email="aarav.notif@smartcollege.edu",
            is_active=True,
        )

        self.hostel = Hostel.objects.create(
            name="Tagore Hostel",
            code="TAGORE-H",
            hostel_type="BOYS",
            is_active=True,
        )
        HostelWarden.objects.create(
            user=self.warden,
            hostel=self.hostel,
            role="WARDEN",
            is_active=True,
        )
        self.block = HostelBlock.objects.create(hostel=self.hostel, name="Block A", code="A")
        self.floor = HostelFloor.objects.create(block=self.block, name="Ground Floor", floor_number=0)
        self.room1 = HostelRoom.objects.create(
            hostel=self.hostel,
            block=self.block,
            floor=self.floor,
            room_number="101",
            capacity=2,
            monthly_rent=4000,
        )
        self.bed1 = HostelBed.objects.create(room=self.room1, bed_number="B1", status="AVAILABLE")
        self.bed2 = HostelBed.objects.create(room=self.room1, bed_number="B2", status="AVAILABLE")
        self.room2 = HostelRoom.objects.create(
            hostel=self.hostel,
            block=self.block,
            floor=self.floor,
            room_number="102",
            capacity=2,
            monthly_rent=4000,
        )
        self.bed3 = HostelBed.objects.create(room=self.room2, bed_number="B1", status="AVAILABLE")

    def test_application_submission_triggers_notification(self):
        """Notification created for student when hostel application is submitted."""
        self.client.login(username="notif_student", password="studentpassword123")
        post_data = {
            "hostel_preference": self.hostel.id,
            "room_type_preference": "DOUBLE",
            "academic_year": "2026-27",
            "reason": "Living far from college",
        }
        resp = self.client.post("/hostel/applications/create/", post_data)
        self.assertEqual(resp.status_code, 302)

        notif = Notification.objects.filter(
            recipient=self.student_user,
            title="Hostel Application Submitted",
        ).last()
        self.assertIsNotNone(notif)
        self.assertIn("Tagore Hostel", notif.message)

    def test_application_approved_and_rejected_notifications(self):
        """Notification created for student when warden approves or rejects application."""
        app = HostelApplication.objects.create(
            student=self.student,
            hostel_preference=self.hostel,
            room_type_preference="DOUBLE",
            academic_year="2026-27",
            status="PENDING",
        )

        # 1. Approval
        self.client.login(username="notif_warden", password="wardenpassword123")
        self.client.post(
            f"/hostel/admin/applications/{app.pk}/review/",
            {"action": "APPROVED", "remarks": "Eligible candidate"},
        )
        notif_app = Notification.objects.filter(
            recipient=self.student_user,
            title="Hostel Application Approved",
        ).last()
        self.assertIsNotNone(notif_app)
        self.assertIn("approved", notif_app.message)

        # 2. Rejection
        self.client.post(
            f"/hostel/admin/applications/{app.pk}/review/",
            {"action": "REJECTED", "remarks": "No capacity", "rejection_reason": "Distance criteria not met"},
        )
        notif_rej = Notification.objects.filter(
            recipient=self.student_user,
            title="Hostel Application Rejected",
        ).last()
        self.assertIsNotNone(notif_rej)
        self.assertIn("rejected", notif_rej.message)

    def test_allocation_completed_notification(self):
        """Notification created for student when bed is allocated."""
        self.client.login(username="notif_admin", password="adminpassword123")
        post_data = {
            "student": self.student.id,
            "hostel": self.hostel.id,
            "room": self.room1.id,
            "bed": self.bed1.id,
            "academic_year": "2026-27",
            "allocation_date": "2026-10-01",
        }
        resp = self.client.post("/hostel/admin/allocations/create/", post_data)
        self.assertEqual(resp.status_code, 302)

        notif = Notification.objects.filter(
            recipient=self.student_user,
            title="Hostel Allocation Completed",
        ).last()
        self.assertIsNotNone(notif)
        self.assertIn("Room 101", notif.message)
        self.assertIn("Bed B1", notif.message)

    def test_checkin_and_checkout_notifications(self):
        """Notification created for student when check-in and check-out are recorded."""
        alloc = HostelAllocation.objects.create(
            student=self.student,
            hostel=self.hostel,
            block=self.block,
            floor=self.floor,
            room=self.room1,
            bed=self.bed1,
            status="ACTIVE",
            academic_year="2026-27",
            allocation_date=timezone.now().date(),
        )

        self.client.login(username="notif_warden", password="wardenpassword123")

        # Check-in
        self.client.post(
            f"/hostel/admin/allocations/{alloc.pk}/event/",
            {"event_type": "CHECK_IN", "event_date": "2026-10-01", "event_time": "09:00", "reason": "Beginning semester"},
        )
        notif_in = Notification.objects.filter(
            recipient=self.student_user,
            title="Hostel Check-in Completed",
        ).last()
        self.assertIsNotNone(notif_in)
        self.assertIn("check-in", notif_in.message.lower())

        # Check-out
        self.client.post(
            f"/hostel/admin/allocations/{alloc.pk}/event/",
            {"event_type": "CHECK_OUT", "event_date": "2026-10-05", "event_time": "17:00", "reason": "Vacating semester end"},
        )
        notif_out = Notification.objects.filter(
            recipient=self.student_user,
            title="Hostel Check-out Completed",
        ).last()
        self.assertIsNotNone(notif_out)
        self.assertIn("check-out", notif_out.message.lower())

    def test_room_transfer_notification(self):
        """Notification created for student when room transfer is processed."""
        alloc = HostelAllocation.objects.create(
            student=self.student,
            hostel=self.hostel,
            block=self.block,
            floor=self.floor,
            room=self.room1,
            bed=self.bed1,
            status="ACTIVE",
            academic_year="2026-27",
            allocation_date=timezone.now().date(),
        )

        self.client.login(username="notif_warden", password="wardenpassword123")
        post_data = {
            "new_hostel": self.hostel.id,
            "new_room": self.room2.id,
            "new_bed": self.bed3.id,
            "transfer_date": "2026-10-05",
            "reason": "Quiet study environment",
            "remarks": "Approved by warden",
        }
        resp = self.client.post(f"/hostel/admin/allocations/{alloc.pk}/transfer/", post_data)
        self.assertEqual(resp.status_code, 302)

        notif = Notification.objects.filter(
            recipient=self.student_user,
            title="Hostel Room Transfer Completed",
        ).last()
        self.assertIsNotNone(notif)
        self.assertIn("102", notif.message)

    def test_complaint_update_and_resolved_notifications(self):
        """Notification created for student when complaint is updated or resolved."""
        complaint = HostelComplaint.objects.create(
            student=self.student,
            hostel=self.hostel,
            room=self.room1,
            title="Tap leaking in bathroom",
            description="Continuous water dripping",
            category="PLUMBING",
            priority="MEDIUM",
            status="OPEN",
        )

        self.client.login(username="notif_warden", password="wardenpassword123")

        # 1. Update status to IN_PROGRESS
        self.client.post(
            f"/hostel/admin/complaints/{complaint.pk}/",
            {"status": "IN_PROGRESS", "priority": "MEDIUM", "resolution": ""},
        )
        notif_upd = Notification.objects.filter(
            recipient=self.student_user,
            title="Hostel Complaint Updated",
        ).last()
        self.assertIsNotNone(notif_upd)
        self.assertIn("In Progress", notif_upd.message)

        # 2. Resolve complaint
        self.client.post(
            f"/hostel/admin/complaints/{complaint.pk}/",
            {"status": "RESOLVED", "priority": "MEDIUM", "resolution": "Washer replaced by plumber"},
        )
        notif_res = Notification.objects.filter(
            recipient=self.student_user,
            title="Hostel Complaint Resolved",
        ).last()
        self.assertIsNotNone(notif_res)
        self.assertIn("Washer replaced", notif_res.message)

    def test_hostel_notice_published_notification(self):
        """Notification created for active residents when hostel notice is published."""
        # Create active allocation for student
        HostelAllocation.objects.create(
            student=self.student,
            hostel=self.hostel,
            block=self.block,
            floor=self.floor,
            room=self.room1,
            bed=self.bed1,
            status="ACTIVE",
            academic_year="2026-27",
            allocation_date=timezone.now().date(),
        )

        self.client.login(username="notif_warden", password="wardenpassword123")
        post_data = {
            "hostel": self.hostel.id,
            "title": "Curfew Timing Announcement",
            "message": "Hostel gate will close at 9:30 PM sharp tonight due to maintenance.",
            "publish_date": "2026-10-04",
            "priority": "IMPORTANT",
        }
        resp = self.client.post("/hostel/admin/notices/create/", post_data)
        self.assertEqual(resp.status_code, 302)

        notif = Notification.objects.filter(
            recipient=self.student_user,
            title__startswith="Hostel Notice: Curfew Timing Announcement",
        ).last()
        self.assertIsNotNone(notif)
        self.assertIn("9:30 PM", notif.message)


class HostelSecurityAndPermissionsTests(TestCase):
    def setUp(self):
        from students.models import Department, Student
        self.admin = User.objects.create_superuser(
            username="sec_superadmin", password="adminpassword123", email="secadmin@smartcollege.edu"
        )
        self.warden1 = User.objects.create_user(
            username="sec_warden1", password="wardenpassword123", email="warden1@smartcollege.edu"
        )
        self.warden2 = User.objects.create_user(
            username="sec_warden2", password="wardenpassword123", email="warden2@smartcollege.edu"
        )
        self.faculty = User.objects.create_user(
            username="sec_faculty", password="facultypassword123", email="faculty@smartcollege.edu"
        )

        self.student1_user = User.objects.create_user(
            username="student_a", password="studentpassword123", email="stud_a@smartcollege.edu"
        )
        self.student2_user = User.objects.create_user(
            username="student_b", password="studentpassword123", email="stud_b@smartcollege.edu"
        )

        self.dept, _ = Department.objects.get_or_create(name="Security Testing Dept")
        self.student_a = Student.objects.create(
            user=self.student1_user,
            name="Student Alice",
            roll_no="SEC-A",
            department=self.dept,
            year=1,
            email="alice@smartcollege.edu",
            is_active=True,
        )
        self.student_b = Student.objects.create(
            user=self.student2_user,
            name="Student Bob",
            roll_no="SEC-B",
            department=self.dept,
            year=1,
            email="bob@smartcollege.edu",
            is_active=True,
        )

        # Hostel 1 & 2
        self.hostel1 = Hostel.objects.create(
            name="Kalam Boys Hostel", code="KALAM-H", hostel_type="BOYS", is_active=True
        )
        self.hostel2 = Hostel.objects.create(
            name="Sarabhai Girls Hostel", code="SARABHAI-H", hostel_type="GIRLS", is_active=True
        )

        # Warden Assignments
        HostelWarden.objects.create(user=self.warden1, hostel=self.hostel1, role="WARDEN", is_active=True)
        HostelWarden.objects.create(user=self.warden2, hostel=self.hostel2, role="WARDEN", is_active=True)

        # Rooms & Beds
        b1 = HostelBlock.objects.create(hostel=self.hostel1, name="B1", code="B1")
        f1 = HostelFloor.objects.create(block=b1, name="F1", floor_number=1)
        self.room1 = HostelRoom.objects.create(hostel=self.hostel1, block=b1, floor=f1, room_number="101", capacity=2)
        self.bed1 = HostelBed.objects.create(room=self.room1, bed_number="A1", status="OCCUPIED")

        b2 = HostelBlock.objects.create(hostel=self.hostel2, name="B2", code="B2")
        f2 = HostelFloor.objects.create(block=b2, name="F1", floor_number=1)
        self.room2 = HostelRoom.objects.create(hostel=self.hostel2, block=b2, floor=f2, room_number="201", capacity=2)
        self.bed2 = HostelBed.objects.create(room=self.room2, bed_number="B1", status="OCCUPIED")

        # Applications
        self.app_a = HostelApplication.objects.create(
            student=self.student_a,
            hostel_preference=self.hostel1,
            room_type_preference="DOUBLE",
            academic_year="2026-27",
            status="APPROVED",
        )
        self.app_b = HostelApplication.objects.create(
            student=self.student_b,
            hostel_preference=self.hostel2,
            room_type_preference="DOUBLE",
            academic_year="2026-27",
            status="APPROVED",
        )

        # Allocations
        self.alloc_a = HostelAllocation.objects.create(
            student=self.student_a,
            hostel=self.hostel1,
            block=b1,
            floor=f1,
            room=self.room1,
            bed=self.bed1,
            status="ACTIVE",
            academic_year="2026-27",
            allocation_date=timezone.now().date(),
        )
        self.alloc_b = HostelAllocation.objects.create(
            student=self.student_b,
            hostel=self.hostel2,
            block=b2,
            floor=f2,
            room=self.room2,
            bed=self.bed2,
            status="ACTIVE",
            academic_year="2026-27",
            allocation_date=timezone.now().date(),
        )

        # Complaints
        self.comp_a = HostelComplaint.objects.create(
            student=self.student_a,
            hostel=self.hostel1,
            room=self.room1,
            title="Alice Room Water Issue",
            description="Faucet leaking",
            category="PLUMBING",
            priority="LOW",
            status="OPEN",
        )
        self.comp_b = HostelComplaint.objects.create(
            student=self.student_b,
            hostel=self.hostel2,
            room=self.room2,
            title="Bob Room Electrical Issue",
            description="Light flickering",
            category="ELECTRICAL",
            priority="LOW",
            status="OPEN",
        )

    def test_admin_full_access(self):
        """Superuser has full administrative access to all hostels, allocations, and applications."""
        self.client.login(username="sec_superadmin", password="adminpassword123")

        # Can view both applications
        resp1 = self.client.get(f"/hostel/applications/{self.app_a.pk}/")
        self.assertEqual(resp1.status_code, 200)
        resp2 = self.client.get(f"/hostel/applications/{self.app_b.pk}/")
        self.assertEqual(resp2.status_code, 200)

        # Can view both allocations
        resp3 = self.client.get(f"/hostel/admin/allocations/{self.alloc_a.pk}/")
        self.assertEqual(resp3.status_code, 200)
        resp4 = self.client.get(f"/hostel/admin/allocations/{self.alloc_b.pk}/")
        self.assertEqual(resp4.status_code, 200)

        # Can access reports hub
        resp5 = self.client.get("/hostel/admin/reports/")
        self.assertEqual(resp5.status_code, 200)

    def test_warden_hostel_isolation(self):
        """Warden of Hostel 1 cannot view or modify allocations/applications of Hostel 2."""
        self.client.login(username="sec_warden1", password="wardenpassword123")

        # Can access own hostel application
        resp1 = self.client.get(f"/hostel/applications/{self.app_a.pk}/")
        self.assertEqual(resp1.status_code, 200)

        # CANNOT access other hostel application (403 Forbidden)
        resp2 = self.client.get(f"/hostel/applications/{self.app_b.pk}/")
        self.assertEqual(resp2.status_code, 403)

        # Can access own hostel allocation
        resp3 = self.client.get(f"/hostel/admin/allocations/{self.alloc_a.pk}/")
        self.assertEqual(resp3.status_code, 200)

        # CANNOT access other hostel allocation (403 Forbidden)
        resp4 = self.client.get(f"/hostel/admin/allocations/{self.alloc_b.pk}/")
        self.assertEqual(resp4.status_code, 403)

        # CANNOT review other hostel application (403 Forbidden)
        resp5 = self.client.post(
            f"/hostel/admin/applications/{self.app_b.pk}/review/",
            {"action": "APPROVED", "remarks": "Unauthorized attempt"},
        )
        self.assertEqual(resp5.status_code, 403)

    def test_student_isolation_prevents_direct_url_manipulation(self):
        """Student A cannot access Student B's applications or complaints via direct URL tampering."""
        self.client.login(username="student_a", password="studentpassword123")

        # Alice can view own application
        resp1 = self.client.get(f"/hostel/applications/{self.app_a.pk}/")
        self.assertEqual(resp1.status_code, 200)
        self.assertContains(resp1, self.app_a.application_id)

        # Alice CANNOT view Bob's application (direct URL tampering returns 403)
        resp2 = self.client.get(f"/hostel/applications/{self.app_b.pk}/")
        self.assertEqual(resp2.status_code, 403)

        # Alice can view own complaint
        resp3 = self.client.get(f"/hostel/complaints/{self.comp_a.pk}/")
        self.assertEqual(resp3.status_code, 200)

        # Alice CANNOT view Bob's complaint (direct URL tampering returns 403)
        resp4 = self.client.get(f"/hostel/complaints/{self.comp_b.pk}/")
        self.assertEqual(resp4.status_code, 403)

    def test_unauthorized_faculty_denied_access(self):
        """General faculty member without warden role cannot access hostel administrative views."""
        self.client.login(username="sec_faculty", password="facultypassword123")

        # Denied from admin allocations (403)
        resp1 = self.client.get("/hostel/admin/allocations/")
        self.assertEqual(resp1.status_code, 403)

        # Denied from reports hub (403)
        resp2 = self.client.get("/hostel/admin/reports/")
        self.assertEqual(resp2.status_code, 403)

        # Denied from viewing student applications (403)
        resp3 = self.client.get(f"/hostel/applications/{self.app_a.pk}/")
        self.assertEqual(resp3.status_code, 403)

        # Denied from viewing student complaints (403)
        resp4 = self.client.get(f"/hostel/complaints/{self.comp_a.pk}/")
        self.assertEqual(resp4.status_code, 403)

        # Portal redirects safely if no student profile
        resp5 = self.client.get("/hostel/")
        self.assertEqual(resp5.status_code, 302)


class HostelDataConsistencyAndPerformanceTests(TestCase):
    def setUp(self):
        from students.models import Student, Department
        self.admin = User.objects.create_superuser(
            username="perf_admin",
            password="adminpassword123",
            email="perf_admin@smartcollege.edu",
        )
        self.dept, _ = Department.objects.get_or_create(name="Computer Science")
        self.u1 = User.objects.create_user(username="perf_stud1", password="password123")
        self.stud1 = Student.objects.create(
            user=self.u1,
            name="Alice Walker",
            roll_no="PERF-001",
            department=self.dept,
            year=1,
            email="perf1@smartcollege.edu",
        )
        self.u2 = User.objects.create_user(username="perf_stud2", password="password123")
        self.stud2 = Student.objects.create(
            user=self.u2,
            name="Bob Smith",
            roll_no="PERF-002",
            department=self.dept,
            year=1,
            email="perf2@smartcollege.edu",
        )

        self.hostel1 = Hostel.objects.create(
            name="Consistency Hostel Alpha",
            code="CHA-01",
            hostel_type="BOYS",
        )
        self.block1 = HostelBlock.objects.create(hostel=self.hostel1, name="Alpha Block", code="AB-1")
        self.floor1 = HostelFloor.objects.create(block=self.block1, name="Alpha Floor 1", floor_number=1)
        self.room1 = HostelRoom.objects.create(
            hostel=self.hostel1,
            block=self.block1,
            floor=self.floor1,
            room_number="A-101",
            capacity=2,
        )
        self.bed1a = HostelBed.objects.create(room=self.room1, bed_number="A-101-1")
        self.bed1b = HostelBed.objects.create(room=self.room1, bed_number="A-101-2")

        # Second room for transfer test
        self.room2 = HostelRoom.objects.create(
            hostel=self.hostel1,
            block=self.block1,
            floor=self.floor1,
            room_number="A-102",
            capacity=1,
        )
        self.bed2a = HostelBed.objects.create(room=self.room2, bed_number="A-102-1")

    def test_allocation_occupies_bed_and_updates_room_occupancy(self):
        """Active allocation automatically transitions bed to OCCUPIED and room to PARTIALLY_OCCUPIED / FULL."""
        self.assertEqual(self.bed1a.status, "AVAILABLE")
        self.assertEqual(self.room1.status, "AVAILABLE")

        alloc = HostelAllocation.objects.create(
            student=self.stud1,
            hostel=self.hostel1,
            block=self.block1,
            floor=self.floor1,
            room=self.room1,
            bed=self.bed1a,
            status="ACTIVE",
            allocated_by=self.admin,
        )

        self.bed1a.refresh_from_db()
        self.room1.refresh_from_db()
        self.assertEqual(self.bed1a.status, "OCCUPIED")
        self.assertEqual(self.room1.status, "PARTIALLY_OCCUPIED")

        # Fill the room with second student
        alloc2 = HostelAllocation.objects.create(
            student=self.stud2,
            hostel=self.hostel1,
            block=self.block1,
            floor=self.floor1,
            room=self.room1,
            bed=self.bed1b,
            status="ACTIVE",
            allocated_by=self.admin,
        )
        self.bed1b.refresh_from_db()
        self.room1.refresh_from_db()
        self.assertEqual(self.bed1b.status, "OCCUPIED")
        self.assertEqual(self.room1.status, "FULL")

    def test_checkout_releases_bed_and_updates_room(self):
        """Checkout lifecycle event atomically marks allocation CHECKED_OUT, releases bed, and updates room."""
        alloc = HostelAllocation.objects.create(
            student=self.stud1,
            hostel=self.hostel1,
            block=self.block1,
            floor=self.floor1,
            room=self.room1,
            bed=self.bed1a,
            status="ACTIVE",
            allocated_by=self.admin,
        )
        self.bed1a.refresh_from_db()
        self.room1.refresh_from_db()
        self.assertEqual(self.bed1a.status, "OCCUPIED")
        self.assertEqual(self.room1.status, "PARTIALLY_OCCUPIED")

        # Process Check Out
        checkout = HostelCheckInOut.objects.create(
            allocation=alloc,
            student=self.stud1,
            event_type="CHECK_OUT",
            event_date=timezone.now().date(),
            processed_by=self.admin,
        )

        alloc.refresh_from_db()
        self.bed1a.refresh_from_db()
        self.room1.refresh_from_db()

        self.assertEqual(alloc.status, "CHECKED_OUT")
        self.assertIsNotNone(alloc.actual_checkout_date)
        self.assertEqual(self.bed1a.status, "AVAILABLE")
        self.assertEqual(self.room1.status, "AVAILABLE")

    def test_transfer_releases_old_bed_and_occupies_new_bed(self):
        """Transfer atomically releases source bed, occupies destination bed, and recomputes occupancies."""
        alloc = HostelAllocation.objects.create(
            student=self.stud1,
            hostel=self.hostel1,
            block=self.block1,
            floor=self.floor1,
            room=self.room1,
            bed=self.bed1a,
            status="ACTIVE",
            allocated_by=self.admin,
        )
        self.bed1a.refresh_from_db()
        self.bed2a.refresh_from_db()
        self.assertEqual(self.bed1a.status, "OCCUPIED")
        self.assertEqual(self.bed2a.status, "AVAILABLE")

        # Transfer from room1/bed1a to room2/bed2a
        transfer = HostelRoomTransfer.objects.create(
            student=self.stud1,
            allocation=alloc,
            old_hostel=self.hostel1,
            old_block=self.block1,
            old_floor=self.floor1,
            old_room=self.room1,
            old_bed=self.bed1a,
            new_hostel=self.hostel1,
            new_block=self.block1,
            new_floor=self.floor1,
            new_room=self.room2,
            new_bed=self.bed2a,
            transfer_date=timezone.now().date(),
            approved_by=self.admin,
            reason="Noise issues in room 101",
        )

        alloc.refresh_from_db()
        self.bed1a.refresh_from_db()
        self.bed2a.refresh_from_db()
        self.room1.refresh_from_db()
        self.room2.refresh_from_db()

        # Old bed released, new bed occupied
        self.assertEqual(self.bed1a.status, "AVAILABLE")
        self.assertEqual(self.bed2a.status, "OCCUPIED")
        self.assertEqual(self.room1.status, "AVAILABLE")
        self.assertEqual(self.room2.status, "FULL")
        self.assertEqual(alloc.room_id, self.room2.id)
        self.assertEqual(alloc.bed_id, self.bed2a.id)

    def test_database_constraints_prevent_duplicate_active_allocation(self):
        """DB UniqueConstraints prevent duplicate active student or bed allocations."""
        HostelAllocation.objects.create(
            student=self.stud1,
            hostel=self.hostel1,
            block=self.block1,
            floor=self.floor1,
            room=self.room1,
            bed=self.bed1a,
            status="ACTIVE",
            allocated_by=self.admin,
        )

        # 1. Prevent duplicate active allocation for the same bed
        with transaction.atomic():
            with self.assertRaises(IntegrityError):
                HostelAllocation.objects.create(
                    student=self.stud2,
                    hostel=self.hostel1,
                    block=self.block1,
                    floor=self.floor1,
                    room=self.room1,
                    bed=self.bed1a,
                    status="ACTIVE",
                    allocated_by=self.admin,
                )

        # 2. Prevent duplicate active allocation for the same student
        with transaction.atomic():
            with self.assertRaises(IntegrityError):
                HostelAllocation.objects.create(
                    student=self.stud1,
                    hostel=self.hostel1,
                    block=self.block1,
                    floor=self.floor1,
                    room=self.room1,
                    bed=self.bed1b,
                    status="ACTIVE",
                    allocated_by=self.admin,
                )

    def test_admin_dashboard_aggregation_performance(self):
        """Dashboard renders efficiently with aggregated KPI counts and charts."""
        # Create an allocation, application, complaint, and attendance
        HostelAllocation.objects.create(
            student=self.stud1,
            hostel=self.hostel1,
            block=self.block1,
            floor=self.floor1,
            room=self.room1,
            bed=self.bed1a,
            status="ACTIVE",
            allocated_by=self.admin,
        )
        HostelApplication.objects.create(
            student=self.stud2,
            hostel_preference=self.hostel1,
            room_type_preference="DOUBLE",
            status="PENDING",
        )
        HostelComplaint.objects.create(
            student=self.stud1,
            hostel=self.hostel1,
            room=self.room1,
            category="ELECTRICAL",
            title="Light flickering",
            description="Room tube light flickers",
            status="OPEN",
        )
        HostelAttendance.objects.create(
            student=self.stud1,
            hostel=self.hostel1,
            room=self.room1,
            date=timezone.now().date(),
            status="PRESENT",
            marked_by=self.admin,
        )

        self.client.login(username="perf_admin", password="adminpassword123")
        response = self.client.get("/hostel/dashboard/")
        self.assertEqual(response.status_code, 200)

        kpi = response.context["kpi"]
        self.assertEqual(kpi["total_hostels"], 1)
        self.assertEqual(kpi["total_rooms"], 2)
        self.assertEqual(kpi["total_beds"], 3)
        self.assertEqual(kpi["occupied_beds"], 1)
        self.assertEqual(kpi["available_beds"], 2)
        self.assertEqual(kpi["active_residents"], 1)
        self.assertEqual(kpi["pending_applications"], 1)
        self.assertEqual(kpi["open_complaints"], 1)


class HostelFinalIntegrationTests(TestCase):
    def setUp(self):
        from students.models import Student, Department
        self.admin = User.objects.create_superuser(
            username="integ_admin",
            password="adminpassword123",
            email="integ_admin@smartcollege.edu",
        )
        self.dept, _ = Department.objects.get_or_create(name="Mechanical Engineering")
        self.student_user = User.objects.create_user(username="integ_student", password="password123")
        self.student = Student.objects.create(
            user=self.student_user,
            name="Charlie Brown",
            roll_no="INT-001",
            department=self.dept,
            year=1,
            email="charlie@smartcollege.edu",
        )
        self.hostel = Hostel.objects.create(
            name="Visvesvaraya Hostel",
            code="VH-01",
            hostel_type="BOYS",
        )

    def test_admin_dashboard_integration(self):
        """Admin dashboard displays Hostel quick action links and Hostel overview card."""
        self.client.login(username="integ_admin", password="adminpassword123")
        response = self.client.get("/accounts/admin-dashboard/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Hostel & Campus Residences")
        self.assertContains(response, "/hostel/dashboard/")

    def test_fees_dashboard_hostel_link(self):
        """Fees dashboard displays link to Hostel Fee Records."""
        self.client.login(username="integ_admin", password="adminpassword123")
        response = self.client.get("/fees/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "/hostel/fees/")

    def test_analytics_navigation_hostel_tab(self):
        """Analytics subnavigation tabs contain Hostel & Residence tab."""
        self.client.login(username="integ_admin", password="adminpassword123")
        response = self.client.get("/analytics/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Hostel & Residence")
        self.assertContains(response, "/hostel/dashboard/")

    def test_student_dashboard_integration(self):
        """Student dashboard renders hostel portal section with live summary data."""
        self.client.login(username="integ_student", password="password123")
        response = self.client.get("/students/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Hostel Accommodation")
        self.assertContains(response, "/hostel/")









