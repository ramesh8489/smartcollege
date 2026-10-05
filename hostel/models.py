from django.db import models, transaction
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.utils import timezone


class Hostel(models.Model):
    HOSTEL_TYPE_CHOICES = [
        ("BOYS", "Boys Hostel"),
        ("GIRLS", "Girls Hostel"),
        ("COED", "Co-Ed Hostel"),
    ]

    name = models.CharField(max_length=150)
    code = models.CharField(max_length=30, unique=True)
    hostel_type = models.CharField(max_length=20, choices=HOSTEL_TYPE_CHOICES, default="BOYS")
    address = models.TextField(blank=True)
    contact_phone = models.CharField(max_length=30, blank=True)
    contact_email = models.EmailField(blank=True)
    warden_incharge = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="managed_hostels",
        help_text="Primary faculty or staff warden responsible for this hostel",
    )
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "Hostel"
        verbose_name_plural = "Hostels"

    def __str__(self):
        return f"{self.name} ({self.code})"

    @property
    def total_rooms(self):
        return self.rooms.filter(is_active=True).count()

    @property
    def total_beds(self):
        return HostelBed.objects.filter(room__hostel=self, is_active=True).count()

    @property
    def occupied_beds(self):
        return HostelBed.objects.filter(room__hostel=self, is_active=True, status="OCCUPIED").count()

    @property
    def available_beds(self):
        return HostelBed.objects.filter(room__hostel=self, is_active=True, status="AVAILABLE").count()

    @property
    def occupancy_percentage(self):
        tot = self.total_beds
        if not tot:
            return 0.0
        return round((self.occupied_beds / tot) * 100, 1)


class HostelBlock(models.Model):
    hostel = models.ForeignKey(Hostel, on_delete=models.CASCADE, related_name="blocks")
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=30)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [("hostel", "code")]
        ordering = ["name"]
        verbose_name = "Hostel Block"
        verbose_name_plural = "Hostel Blocks"

    def __str__(self):
        return f"{self.hostel.code} - {self.name} ({self.code})"


class HostelFloor(models.Model):
    block = models.ForeignKey(HostelBlock, on_delete=models.CASCADE, related_name="floors")
    name = models.CharField(max_length=50, help_text="e.g. Ground Floor, 1st Floor")
    floor_number = models.IntegerField(default=0)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [("block", "floor_number")]
        ordering = ["floor_number"]
        verbose_name = "Hostel Floor"
        verbose_name_plural = "Hostel Floors"

    def __str__(self):
        return f"{self.block} - {self.name}"


class HostelRoom(models.Model):
    ROOM_TYPE_CHOICES = [
        ("SINGLE", "Single"),
        ("DOUBLE", "Double"),
        ("TRIPLE", "Triple"),
        ("FOUR_SHARING", "Four Sharing"),
        ("DORMITORY", "Dormitory"),
        ("OTHER", "Other"),
    ]

    ROOM_STATUS_CHOICES = [
        ("AVAILABLE", "Available"),
        ("PARTIALLY_OCCUPIED", "Partially Occupied"),
        ("FULL", "Full"),
        ("MAINTENANCE", "Maintenance"),
        ("INACTIVE", "Inactive"),
    ]

    hostel = models.ForeignKey(Hostel, on_delete=models.CASCADE, related_name="rooms")
    block = models.ForeignKey(HostelBlock, on_delete=models.CASCADE, related_name="rooms")
    floor = models.ForeignKey(HostelFloor, on_delete=models.CASCADE, related_name="rooms")
    room_number = models.CharField(max_length=30)
    room_type = models.CharField(max_length=20, choices=ROOM_TYPE_CHOICES, default="DOUBLE")
    capacity = models.PositiveIntegerField(default=2)
    status = models.CharField(max_length=25, choices=ROOM_STATUS_CHOICES, default="AVAILABLE")
    monthly_rent = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0.00,
        help_text="Standard monthly or term fee per resident",
    )
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [("block", "room_number")]
        ordering = ["room_number"]
        verbose_name = "Hostel Room"
        verbose_name_plural = "Hostel Rooms"

    def __str__(self):
        return f"{self.hostel.code} - Rm {self.room_number} ({self.get_room_type_display()})"

    def clean(self):
        super().clean()
        if self.block and self.hostel and self.block.hostel_id != self.hostel_id:
            raise ValidationError({"block": "Selected block does not belong to the selected hostel."})
        if self.floor and self.block and self.floor.block_id != self.block_id:
            raise ValidationError({"floor": "Selected floor does not belong to the selected block."})

    @property
    def occupied_beds_count(self):
        return self.beds.filter(is_active=True, status="OCCUPIED").count()

    @property
    def available_beds_count(self):
        return self.beds.filter(is_active=True, status="AVAILABLE").count()

    def update_occupancy_status(self):
        """Computes and updates room status based on current bed statuses."""
        if not self.is_active:
            self.status = "INACTIVE"
        elif self.status == "MAINTENANCE":
            pass
        else:
            total_beds = self.beds.filter(is_active=True).count()
            occupied = self.beds.filter(is_active=True, status="OCCUPIED").count()
            if occupied == 0:
                self.status = "AVAILABLE"
            elif occupied >= self.capacity or (total_beds > 0 and occupied >= total_beds):
                self.status = "FULL"
            else:
                self.status = "PARTIALLY_OCCUPIED"
        HostelRoom.objects.filter(pk=self.pk).update(status=self.status)


class HostelBed(models.Model):
    BED_STATUS_CHOICES = [
        ("AVAILABLE", "Available"),
        ("OCCUPIED", "Occupied"),
        ("MAINTENANCE", "Maintenance"),
        ("RESERVED", "Reserved"),
    ]

    room = models.ForeignKey(HostelRoom, on_delete=models.CASCADE, related_name="beds")
    bed_number = models.CharField(max_length=30, help_text="e.g. Bed-1, B1, A")
    status = models.CharField(max_length=20, choices=BED_STATUS_CHOICES, default="AVAILABLE")
    is_active = models.BooleanField(default=True)
    remarks = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [("room", "bed_number")]
        ordering = ["bed_number"]
        verbose_name = "Hostel Bed"
        verbose_name_plural = "Hostel Beds"

    def __str__(self):
        return f"{self.room.room_number} - {self.bed_number} ({self.get_status_display()})"

    def clean(self):
        super().clean()
        if not self.pk and self.room_id:
            current_count = self.room.beds.count()
            if current_count >= self.room.capacity:
                raise ValidationError(
                    f"Room {self.room.room_number} has reached its designated capacity of {self.room.capacity} beds."
                )

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if self.room_id:
            self.room.update_occupancy_status()


class HostelApplication(models.Model):
    STATUS_CHOICES = [
        ("PENDING", "Pending"),
        ("UNDER_REVIEW", "Under Review"),
        ("APPROVED", "Approved"),
        ("REJECTED", "Rejected"),
        ("WAITLISTED", "Waitlisted"),
        ("CANCELLED", "Cancelled"),
    ]

    application_id = models.CharField(max_length=32, unique=True, editable=False)
    student = models.ForeignKey(
        "students.Student",
        on_delete=models.CASCADE,
        related_name="hostel_applications",
    )
    hostel_preference = models.ForeignKey(
        Hostel,
        on_delete=models.CASCADE,
        related_name="applications",
        verbose_name="Preferred Hostel",
    )
    room_type_preference = models.CharField(
        max_length=20,
        choices=HostelRoom.ROOM_TYPE_CHOICES,
        default="DOUBLE",
    )
    academic_year = models.CharField(max_length=20, default="2026-27")
    application_date = models.DateField(default=timezone.now)
    reason = models.TextField(blank=True, help_text="Reason for requesting hostel accommodation")
    remarks = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="PENDING")
    reviewed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reviewed_hostel_applications",
    )
    reviewed_date = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Hostel Application"
        verbose_name_plural = "Hostel Applications"

    def __str__(self):
        return f"{self.application_id} - {self.student.name} ({self.get_status_display()})"

    def save(self, *args, **kwargs):
        if not self.application_id:
            year = timezone.now().year
            prefix = f"HOSTEL-APP-{year}-"
            last = HostelApplication.objects.filter(application_id__startswith=prefix).order_by("-id").first()
            if last and last.application_id:
                try:
                    last_seq = int(last.application_id.split("-")[-1])
                    next_seq = last_seq + 1
                except (ValueError, IndexError):
                    next_seq = HostelApplication.objects.count() + 1
            else:
                next_seq = 1
            self.application_id = f"{prefix}{next_seq:06d}"
        super().save(*args, **kwargs)


class HostelAllocation(models.Model):
    STATUS_CHOICES = [
        ("ACTIVE", "Active"),
        ("TRANSFERRED", "Transferred"),
        ("CHECKED_OUT", "Checked Out"),
        ("CANCELLED", "Cancelled"),
    ]

    allocation_id = models.CharField(max_length=32, unique=True, editable=False)
    student = models.ForeignKey(
        "students.Student",
        on_delete=models.CASCADE,
        related_name="hostel_allocations",
    )
    hostel = models.ForeignKey(
        Hostel,
        on_delete=models.CASCADE,
        related_name="allocations",
    )
    block = models.ForeignKey(
        HostelBlock,
        on_delete=models.CASCADE,
        related_name="allocations",
    )
    floor = models.ForeignKey(
        HostelFloor,
        on_delete=models.CASCADE,
        related_name="allocations",
    )
    room = models.ForeignKey(
        HostelRoom,
        on_delete=models.CASCADE,
        related_name="allocations",
    )
    bed = models.ForeignKey(
        HostelBed,
        on_delete=models.CASCADE,
        related_name="allocations",
    )
    allocation_date = models.DateField(default=timezone.now)
    expected_checkout_date = models.DateField(null=True, blank=True)
    actual_checkout_date = models.DateField(null=True, blank=True)
    academic_year = models.CharField(max_length=20, default="2026-27")
    semester = models.PositiveIntegerField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="ACTIVE")
    allocated_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="allocated_hostel_students",
    )
    remarks = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-allocation_date", "-created_at"]
        verbose_name = "Hostel Allocation"
        verbose_name_plural = "Hostel Allocations"
        constraints = [
            models.UniqueConstraint(
                fields=["student"],
                condition=models.Q(status="ACTIVE"),
                name="unique_active_student_hostel_allocation",
            ),
            models.UniqueConstraint(
                fields=["bed"],
                condition=models.Q(status="ACTIVE"),
                name="unique_active_bed_hostel_allocation",
            ),
        ]

    def __str__(self):
        return f"{self.allocation_id} - {self.student.name} ({self.room.room_number}/{self.bed.bed_number})"

    def clean(self):
        super().clean()
        if self.status == "ACTIVE":
            # Check student doesn't have another active allocation
            if self.student_id:
                existing_student_alloc = HostelAllocation.objects.filter(
                    student_id=self.student_id,
                    status="ACTIVE",
                ).exclude(pk=self.pk).first()
                if existing_student_alloc:
                    raise ValidationError({
                        "student": f"Student {self.student.name} already has an active allocation ({existing_student_alloc.allocation_id})."
                    })

            # Check bed status
            if self.bed_id:
                if not self.bed.is_active:
                    raise ValidationError({"bed": "Selected bed is currently marked inactive."})
                if self.bed.status == "MAINTENANCE":
                    raise ValidationError({"bed": "Selected bed is currently under maintenance."})
                if self.bed.status == "OCCUPIED" and not (self.pk and HostelAllocation.objects.filter(pk=self.pk, bed_id=self.bed_id).exists()):
                    raise ValidationError({"bed": f"Bed {self.bed.bed_number} is already occupied."})

            # Check room status
            if self.room_id:
                if not self.room.is_active:
                    raise ValidationError({"room": "Selected room is currently marked inactive."})
                if self.room.status == "MAINTENANCE":
                    raise ValidationError({"room": "Selected room is currently under maintenance."})

        # Consistency checks
        if self.bed_id and self.room_id and self.bed.room_id != self.room_id:
            raise ValidationError({"bed": "Selected bed does not belong to the selected room."})
        if self.room_id and self.floor_id and self.room.floor_id != self.floor_id:
            raise ValidationError({"room": "Selected room does not belong to the selected floor."})
        if self.floor_id and self.block_id and self.floor.block_id != self.block_id:
            raise ValidationError({"floor": "Selected floor does not belong to the selected block."})
        if self.block_id and self.hostel_id and self.block.hostel_id != self.hostel_id:
            raise ValidationError({"block": "Selected block does not belong to the selected hostel."})

    def save(self, *args, **kwargs):
        if not self.allocation_id:
            year = timezone.now().year
            prefix = f"HOSTEL-ALLOC-{year}-"
            last = HostelAllocation.objects.filter(allocation_id__startswith=prefix).order_by("-id").first()
            if last and last.allocation_id:
                try:
                    last_seq = int(last.allocation_id.split("-")[-1])
                    next_seq = last_seq + 1
                except (ValueError, IndexError):
                    next_seq = HostelAllocation.objects.count() + 1
            else:
                next_seq = 1
            self.allocation_id = f"{prefix}{next_seq:06d}"

        with transaction.atomic():
            super().save(*args, **kwargs)
            if self.bed_id:
                if self.status == "ACTIVE":
                    if self.bed.status != "OCCUPIED":
                        HostelBed.objects.filter(pk=self.bed_id).update(status="OCCUPIED")
                elif self.status in ("CHECKED_OUT", "CANCELLED", "TRANSFERRED"):
                    HostelBed.objects.filter(pk=self.bed_id).update(status="AVAILABLE")
                if self.room_id:
                    self.room.update_occupancy_status()


class HostelCheckInOut(models.Model):
    EVENT_CHOICES = [
        ("CHECK_IN", "Check In"),
        ("CHECK_OUT", "Check Out"),
    ]

    allocation = models.ForeignKey(
        HostelAllocation,
        on_delete=models.CASCADE,
        related_name="lifecycle_events",
    )
    student = models.ForeignKey(
        "students.Student",
        on_delete=models.CASCADE,
        related_name="hostel_lifecycle_logs",
    )
    event_type = models.CharField(max_length=20, choices=EVENT_CHOICES)
    event_date = models.DateField(default=timezone.now)
    event_time = models.TimeField(default=timezone.now)
    reason = models.TextField(blank=True, help_text="Reason for checkout or checkin comments")
    processed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="processed_hostel_events",
    )
    remarks = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-event_date", "-created_at"]
        verbose_name = "Hostel Check-in / Check-out"
        verbose_name_plural = "Hostel Check-ins & Check-outs"

    def __str__(self):
        return f"{self.get_event_type_display()} - {self.student.name} ({self.event_date})"

    def save(self, *args, **kwargs):
        with transaction.atomic():
            super().save(*args, **kwargs)
            if self.event_type == "CHECK_OUT":
                self.allocation.status = "CHECKED_OUT"
                self.allocation.actual_checkout_date = self.event_date
                self.allocation.save()


class HostelRoomTransfer(models.Model):
    student = models.ForeignKey(
        "students.Student",
        on_delete=models.CASCADE,
        related_name="hostel_transfers",
    )
    allocation = models.ForeignKey(
        HostelAllocation,
        on_delete=models.CASCADE,
        related_name="transfers",
    )
    old_hostel = models.ForeignKey(
        Hostel,
        on_delete=models.CASCADE,
        related_name="transfers_out",
    )
    old_block = models.ForeignKey(
        HostelBlock,
        on_delete=models.CASCADE,
        related_name="transfers_out",
    )
    old_floor = models.ForeignKey(
        HostelFloor,
        on_delete=models.CASCADE,
        related_name="transfers_out",
    )
    old_room = models.ForeignKey(
        HostelRoom,
        on_delete=models.CASCADE,
        related_name="transfers_out",
    )
    old_bed = models.ForeignKey(
        HostelBed,
        on_delete=models.CASCADE,
        related_name="transfers_out",
    )
    new_hostel = models.ForeignKey(
        Hostel,
        on_delete=models.CASCADE,
        related_name="transfers_in",
    )
    new_block = models.ForeignKey(
        HostelBlock,
        on_delete=models.CASCADE,
        related_name="transfers_in",
    )
    new_floor = models.ForeignKey(
        HostelFloor,
        on_delete=models.CASCADE,
        related_name="transfers_in",
    )
    new_room = models.ForeignKey(
        HostelRoom,
        on_delete=models.CASCADE,
        related_name="transfers_in",
    )
    new_bed = models.ForeignKey(
        HostelBed,
        on_delete=models.CASCADE,
        related_name="transfers_in",
    )
    transfer_date = models.DateField(default=timezone.now)
    reason = models.TextField(help_text="Reason for room/bed transfer request")
    approved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="approved_hostel_transfers",
    )
    remarks = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-transfer_date", "-created_at"]
        verbose_name = "Hostel Room Transfer"
        verbose_name_plural = "Hostel Room Transfers"

    def __str__(self):
        return f"Transfer: {self.student.name} ({self.old_room.room_number}/{self.old_bed.bed_number} -> {self.new_room.room_number}/{self.new_bed.bed_number})"

    def clean(self):
        super().clean()
        if self.old_bed_id and self.new_bed_id and self.old_bed_id == self.new_bed_id:
            raise ValidationError({"new_bed": "New bed cannot be the same as the current assigned bed."})
        if self.new_bed_id:
            if not self.new_bed.is_active or self.new_bed.status != "AVAILABLE":
                raise ValidationError({"new_bed": f"New Bed {self.new_bed.bed_number} is not currently available."})
        if self.new_room_id:
            if not self.new_room.is_active or self.new_room.status in ["MAINTENANCE", "INACTIVE"]:
                raise ValidationError({"new_room": "Selected destination room is not active or under maintenance."})

    def save(self, *args, **kwargs):
        with transaction.atomic():
            super().save(*args, **kwargs)
            # Release old bed
            HostelBed.objects.filter(pk=self.old_bed_id).update(status="AVAILABLE")
            self.old_room.update_occupancy_status()

            # Occupy new bed
            HostelBed.objects.filter(pk=self.new_bed_id).update(status="OCCUPIED")
            self.new_room.update_occupancy_status()

            # Update allocation
            self.allocation.hostel = self.new_hostel
            self.allocation.block = self.new_block
            self.allocation.floor = self.new_floor
            self.allocation.room = self.new_room
            self.allocation.bed = self.new_bed
            self.allocation.save()


class HostelAttendance(models.Model):
    STATUS_CHOICES = [
        ("PRESENT", "Present"),
        ("ABSENT", "Absent"),
        ("PERMISSION", "Permission"),
        ("LEAVE", "Leave"),
    ]

    student = models.ForeignKey(
        "students.Student",
        on_delete=models.CASCADE,
        related_name="hostel_attendances",
    )
    hostel = models.ForeignKey(
        Hostel,
        on_delete=models.CASCADE,
        related_name="attendances",
    )
    room = models.ForeignKey(
        HostelRoom,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="attendances",
    )
    date = models.DateField(default=timezone.now)
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="PRESENT",
    )
    marked_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="marked_hostel_attendances",
    )
    remarks = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-date", "student__name"]
        verbose_name = "Hostel Attendance"
        verbose_name_plural = "Hostel Attendances"
        constraints = [
            models.UniqueConstraint(
                fields=["student", "date"],
                name="unique_student_date_hostel_attendance",
            )
        ]

    def __str__(self):
        return f"{self.student.name} - {self.date} - {self.get_status_display()}"


class HostelComplaint(models.Model):
    CATEGORY_CHOICES = [
        ("ELECTRICAL", "Electrical"),
        ("PLUMBING", "Plumbing"),
        ("FURNITURE", "Furniture"),
        ("INTERNET", "Internet"),
        ("CLEANING", "Cleaning"),
        ("WATER", "Water"),
        ("ROOM", "Room"),
        ("OTHER", "Other"),
    ]

    PRIORITY_CHOICES = [
        ("LOW", "Low"),
        ("MEDIUM", "Medium"),
        ("HIGH", "High"),
        ("URGENT", "Urgent"),
    ]

    STATUS_CHOICES = [
        ("OPEN", "Open"),
        ("ASSIGNED", "Assigned"),
        ("IN_PROGRESS", "In Progress"),
        ("RESOLVED", "Resolved"),
        ("CLOSED", "Closed"),
        ("REJECTED", "Rejected"),
    ]

    complaint_id = models.CharField(max_length=32, unique=True, editable=False)
    student = models.ForeignKey(
        "students.Student",
        on_delete=models.CASCADE,
        related_name="hostel_complaints",
    )
    hostel = models.ForeignKey(
        Hostel,
        on_delete=models.CASCADE,
        related_name="complaints",
    )
    room = models.ForeignKey(
        HostelRoom,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="complaints",
    )
    category = models.CharField(max_length=30, choices=CATEGORY_CHOICES, default="OTHER")
    title = models.CharField(max_length=200)
    description = models.TextField()
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default="MEDIUM")
    attachment = models.FileField(upload_to="hostel/complaints/%Y/%m/", null=True, blank=True)
    assigned_staff = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_hostel_complaints",
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="OPEN")
    resolution = models.TextField(blank=True, help_text="Action taken to resolve or reason for rejection")
    resolved_date = models.DateTimeField(null=True, blank=True)
    resolved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="resolved_hostel_complaints",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Hostel Complaint"
        verbose_name_plural = "Hostel Complaints"

    def __str__(self):
        return f"{self.complaint_id} - {self.title} ({self.get_status_display()})"

    def save(self, *args, **kwargs):
        if not self.complaint_id:
            year = timezone.now().year
            prefix = f"HOSTEL-CMP-{year}-"
            last = HostelComplaint.objects.filter(complaint_id__startswith=prefix).order_by("-id").first()
            if last and last.complaint_id:
                try:
                    last_seq = int(last.complaint_id.split("-")[-1])
                    next_seq = last_seq + 1
                except (ValueError, IndexError):
                    next_seq = HostelComplaint.objects.count() + 1
            else:
                next_seq = 1
            self.complaint_id = f"{prefix}{next_seq:06d}"

        if self.status in ["RESOLVED", "CLOSED"] and not self.resolved_date:
            self.resolved_date = timezone.now()

        super().save(*args, **kwargs)


class HostelWarden(models.Model):
    ROLE_CHOICES = [
        ("CHIEF_WARDEN", "Chief Warden"),
        ("WARDEN", "Hostel Warden"),
        ("ASSISTANT_WARDEN", "Assistant Warden"),
        ("CARETAKER", "Hostel Caretaker"),
    ]

    hostel = models.ForeignKey(
        Hostel,
        on_delete=models.CASCADE,
        related_name="warden_assignments",
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="hostel_warden_roles",
    )
    role = models.CharField(max_length=30, choices=ROLE_CHOICES, default="WARDEN")
    designation = models.CharField(max_length=100, blank=True)
    contact_number = models.CharField(max_length=30, blank=True)
    is_active = models.BooleanField(default=True)
    assigned_date = models.DateField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["hostel__name", "role"]
        verbose_name = "Hostel Warden Assignment"
        verbose_name_plural = "Hostel Warden Assignments"
        constraints = [
            models.UniqueConstraint(fields=["hostel", "user"], name="unique_hostel_warden_assignment")
        ]

    def __str__(self):
        return f"{self.user.get_full_name() or self.user.username} - {self.get_role_display()} ({self.hostel.name})"


class HostelNotice(models.Model):
    PRIORITY_CHOICES = [
        ("NORMAL", "Normal"),
        ("IMPORTANT", "Important"),
        ("URGENT", "Urgent"),
    ]

    hostel = models.ForeignKey(
        Hostel,
        on_delete=models.CASCADE,
        related_name="notices",
    )
    title = models.CharField(max_length=200)
    message = models.TextField()
    publish_date = models.DateField(default=timezone.now)
    expiry_date = models.DateField(null=True, blank=True)
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default="NORMAL")
    attachment = models.FileField(upload_to="hostel/notices/%Y/%m/", null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="published_hostel_notices",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-publish_date", "-created_at"]
        verbose_name = "Hostel Notice"
        verbose_name_plural = "Hostel Notices"

    def __str__(self):
        return f"[{self.hostel.code}] {self.title}"


class HostelVisitor(models.Model):
    """
    Phase 13: Visitor Management model recording visitor entries, relationships,
    dates, entry/exit timestamps, and warden/admin approval.
    """
    STATUS_CHOICES = [
        ("PENDING", "Pending Approval"),
        ("APPROVED", "Approved"),
        ("CHECKED_IN", "Checked In"),
        ("CHECKED_OUT", "Checked Out"),
        ("REJECTED", "Rejected"),
    ]

    student = models.ForeignKey(
        "students.Student",
        on_delete=models.CASCADE,
        related_name="hostel_visitors",
    )
    hostel = models.ForeignKey(
        Hostel,
        on_delete=models.CASCADE,
        related_name="visitors",
    )
    visitor_name = models.CharField(max_length=120)
    relationship = models.CharField(max_length=60, help_text="e.g. Parent, Guardian, Sibling, Friend")
    phone = models.CharField(max_length=20)
    visit_date = models.DateField(default=timezone.now)
    entry_time = models.TimeField(null=True, blank=True)
    exit_time = models.TimeField(null=True, blank=True)
    purpose = models.CharField(max_length=255)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="PENDING")
    approved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="approved_hostel_visitors",
    )
    remarks = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-visit_date", "-created_at"]
        verbose_name = "Hostel Visitor"
        verbose_name_plural = "Hostel Visitors"

    def __str__(self):
        return f"{self.visitor_name} ({self.relationship}) -> {self.student.name} [{self.hostel.code}]"

