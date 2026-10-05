import uuid
from decimal import Decimal
from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator
from django.core.exceptions import ValidationError
from django.utils import timezone
from students.models import Student


def generate_transport_application_id():
    """Generates unique ID: TR-APP-YYYY-XXXXXX"""
    year = timezone.now().year
    random_suffix = uuid.uuid4().hex[:6].upper()
    return f"TR-APP-{year}-{random_suffix}"


def generate_transport_allocation_id():
    """Generates unique ID: TR-ALLOC-YYYY-XXXXXX"""
    year = timezone.now().year
    random_suffix = uuid.uuid4().hex[:6].upper()
    return f"TR-ALLOC-{year}-{random_suffix}"


def generate_transport_pass_number():
    """Generates unique Pass Number: TP-YYYY-XXXXXX"""
    year = timezone.now().year
    random_suffix = uuid.uuid4().hex[:6].upper()
    return f"TP-{year}-{random_suffix}"


def generate_transport_complaint_id():
    """Generates unique Complaint ID: TR-COMP-YYYY-XXXXXX"""
    year = timezone.now().year
    random_suffix = uuid.uuid4().hex[:6].upper()
    return f"TR-COMP-{year}-{random_suffix}"


def generate_transport_incident_id():
    """Generates unique Incident ID: TR-INC-YYYY-XXXXXX"""
    year = timezone.now().year
    random_suffix = uuid.uuid4().hex[:6].upper()
    return f"TR-INC-{year}-{random_suffix}"


# ================================================================
# 1. VEHICLE
# ================================================================
class Vehicle(models.Model):
    VEHICLE_TYPE_CHOICES = [
        ("BUS", "College Bus"),
        ("MINI_BUS", "Mini Bus"),
        ("VAN", "Van / Traveler"),
        ("OTHER", "Other"),
    ]

    STATUS_CHOICES = [
        ("ACTIVE", "Active"),
        ("INACTIVE", "Inactive"),
        ("MAINTENANCE", "Under Maintenance"),
    ]

    vehicle_number = models.CharField(max_length=50, unique=True, help_text="e.g. BUS-01 or Fleet ID")
    registration_number = models.CharField(max_length=50, unique=True, help_text="e.g. TN-01-AB-1234")
    vehicle_type = models.CharField(max_length=20, choices=VEHICLE_TYPE_CHOICES, default="BUS")
    bus_name = models.CharField(max_length=100, help_text="Label or route tag, e.g. North Campus Express")
    seating_capacity = models.PositiveIntegerField(default=50, validators=[MinValueValidator(1)])
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="ACTIVE")

    purchase_date = models.DateField(null=True, blank=True)
    insurance_expiry = models.DateField(null=True, blank=True)
    fitness_expiry = models.DateField(null=True, blank=True)
    pollution_expiry = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["vehicle_number"]
        verbose_name = "Vehicle"
        verbose_name_plural = "Vehicles"

    def __str__(self):
        return f"{self.vehicle_number} ({self.registration_number}) - {self.bus_name}"

    @property
    def allocated_count(self):
        return self.allocations.filter(status="ACTIVE").count()

    @property
    def available_seats(self):
        return max(0, self.seating_capacity - self.allocated_count)

    @property
    def occupancy_percentage(self):
        if self.seating_capacity <= 0:
            return 0.0
        return round((self.allocated_count / self.seating_capacity) * 100, 1)

    @property
    def is_insurance_expired(self):
        if not self.insurance_expiry:
            return False
        return self.insurance_expiry < timezone.now().date()

    @property
    def is_fitness_expired(self):
        if not self.fitness_expiry:
            return False
        return self.fitness_expiry < timezone.now().date()

    @property
    def is_pollution_expired(self):
        if not self.pollution_expiry:
            return False
        return self.pollution_expiry < timezone.now().date()

    @property
    def needs_attention(self):
        today = timezone.now().date()
        warning_window = today + timezone.timedelta(days=30)
        for d in [self.insurance_expiry, self.fitness_expiry, self.pollution_expiry]:
            if d and d <= warning_window:
                return True
        return self.status == "MAINTENANCE"


# ================================================================
# 2. ROUTE
# ================================================================
class Route(models.Model):
    name = models.CharField(max_length=150, help_text="e.g. Route 1 - Tambaram to Campus")
    code = models.CharField(max_length=50, unique=True, help_text="e.g. RT-01")
    start_point = models.CharField(max_length=100)
    destination = models.CharField(max_length=100, default="Campus")
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    assigned_vehicle = models.ForeignKey(
        Vehicle,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="routes"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["code"]
        verbose_name = "Route"
        verbose_name_plural = "Routes"

    def __str__(self):
        return f"{self.code} - {self.name}"

    @property
    def stop_count(self):
        return self.stops.filter(is_active=True).count()

    @property
    def total_students(self):
        return self.allocations.filter(status="ACTIVE").count()


# ================================================================
# 3. STOP
# ================================================================
class Stop(models.Model):
    route = models.ForeignKey(Route, on_delete=models.CASCADE, related_name="stops")
    stop_name = models.CharField(max_length=100)
    stop_code = models.CharField(max_length=50, blank=True)
    stop_order = models.PositiveIntegerField(default=1)
    pickup_time = models.TimeField(help_text="Morning pickup time")
    drop_time = models.TimeField(help_text="Evening drop time")
    distance_km = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    fare_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["route", "stop_order"]
        unique_together = [("route", "stop_order")]
        verbose_name = "Stop"
        verbose_name_plural = "Stops"

    def __str__(self):
        return f"{self.route.code} Stop {self.stop_order}: {self.stop_name} ({self.pickup_time.strftime('%I:%M %p')})"


# ================================================================
# 4. DRIVER
# ================================================================
class Driver(models.Model):
    name = models.CharField(max_length=100)
    employee_id = models.CharField(max_length=50, unique=True)
    phone = models.CharField(max_length=20)
    email = models.EmailField(blank=True)
    address = models.TextField(blank=True)
    licence_number = models.CharField(max_length=50, unique=True)
    licence_expiry = models.DateField()
    joining_date = models.DateField(default=timezone.now)
    assigned_vehicle = models.OneToOneField(
        Vehicle,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="driver"
    )
    emergency_contact = models.CharField(max_length=100, blank=True)
    emergency_phone = models.CharField(max_length=20, blank=True)
    is_active = models.BooleanField(default=True)
    notes = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "Driver"
        verbose_name_plural = "Drivers"

    def __str__(self):
        return f"{self.name} ({self.employee_id}) - Lic: {self.licence_number}"

    @property
    def is_licence_expired(self):
        return self.licence_expiry < timezone.now().date()

    @property
    def is_licence_expiring_soon(self):
        today = timezone.now().date()
        return today <= self.licence_expiry <= today + timezone.timedelta(days=30)


# ================================================================
# 5. CONDUCTOR / TRANSPORT STAFF
# ================================================================
class Conductor(models.Model):
    name = models.CharField(max_length=100)
    employee_id = models.CharField(max_length=50, unique=True)
    phone = models.CharField(max_length=20)
    email = models.EmailField(blank=True)
    address = models.TextField(blank=True)
    joining_date = models.DateField(default=timezone.now)
    assigned_vehicle = models.ForeignKey(
        Vehicle,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="conductors"
    )
    assigned_route = models.ForeignKey(
        Route,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="conductors"
    )
    emergency_contact = models.CharField(max_length=100, blank=True)
    emergency_phone = models.CharField(max_length=20, blank=True)
    is_active = models.BooleanField(default=True)
    notes = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "Conductor"
        verbose_name_plural = "Conductors"

    def __str__(self):
        return f"{self.name} ({self.employee_id})"


class TransportStaff(models.Model):
    """Staff or supervisor assigned to transport management."""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="transport_staff_profile")
    role = models.CharField(max_length=50, default="SUPERVISOR")
    phone = models.CharField(max_length=20, blank=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.user.get_full_name() or self.user.username} ({self.role})"


# ================================================================
# 6. STUDENT TRANSPORT APPLICATION
# ================================================================
class TransportApplication(models.Model):
    STATUS_CHOICES = [
        ("PENDING", "Pending Review"),
        ("APPROVED", "Approved"),
        ("REJECTED", "Rejected"),
        ("CANCELLED", "Cancelled"),
    ]

    application_id = models.CharField(max_length=50, unique=True, default=generate_transport_application_id)
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name="transport_applications")
    academic_year = models.CharField(max_length=20, default="2026-27")
    route = models.ForeignKey(Route, on_delete=models.CASCADE, related_name="applications")
    stop = models.ForeignKey(Stop, on_delete=models.CASCADE, related_name="applications")
    application_date = models.DateField(default=timezone.now)
    requested_from_date = models.DateField(default=timezone.now)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="PENDING")

    parent_name = models.CharField(max_length=100, blank=True)
    parent_phone = models.CharField(max_length=20, blank=True)
    student_phone = models.CharField(max_length=20, blank=True)
    address = models.TextField(blank=True)
    remarks = models.TextField(blank=True)

    reviewed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reviewed_transport_applications"
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-application_date", "-created_at"]
        verbose_name = "Transport Application"
        verbose_name_plural = "Transport Applications"

    def __str__(self):
        return f"{self.application_id} - {self.student.name} ({self.status})"

    def clean(self):
        if self.stop_id and self.route_id and self.stop.route_id != self.route_id:
            raise ValidationError({"stop": "Selected stop does not belong to the selected route."})


# ================================================================
# 7. STUDENT BUS ALLOCATION
# ================================================================
class TransportAllocation(models.Model):
    STATUS_CHOICES = [
        ("ACTIVE", "Active"),
        ("INACTIVE", "Inactive"),
        ("CANCELLED", "Cancelled"),
    ]

    allocation_id = models.CharField(max_length=50, unique=True, default=generate_transport_allocation_id)
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name="transport_allocations")
    vehicle = models.ForeignKey(Vehicle, on_delete=models.CASCADE, related_name="allocations")
    route = models.ForeignKey(Route, on_delete=models.CASCADE, related_name="allocations")
    stop = models.ForeignKey(Stop, on_delete=models.CASCADE, related_name="allocations")
    academic_year = models.CharField(max_length=20, default="2026-27")

    pickup_time = models.TimeField(null=True, blank=True)
    drop_time = models.TimeField(null=True, blank=True)
    start_date = models.DateField(default=timezone.now)
    end_date = models.DateField(null=True, blank=True)
    seat_number = models.CharField(max_length=20, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="ACTIVE")

    allocated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    remarks = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-start_date", "-created_at"]
        verbose_name = "Transport Allocation"
        verbose_name_plural = "Transport Allocations"
        constraints = [
            models.UniqueConstraint(
                fields=["student"],
                condition=models.Q(status="ACTIVE"),
                name="unique_active_transport_student"
            )
        ]

    def __str__(self):
        return f"{self.allocation_id} - {self.student.name} -> {self.vehicle.vehicle_number} ({self.route.code})"

    def clean(self):
        if self.stop_id and self.route_id and self.stop.route_id != self.route_id:
            raise ValidationError({"stop": "Selected stop does not belong to the selected route."})
        if self.vehicle_id and self.vehicle.status != "ACTIVE" and self.status == "ACTIVE":
            raise ValidationError({"vehicle": f"Vehicle {self.vehicle.vehicle_number} is {self.vehicle.get_status_display()} and cannot accept new allocations."})
        if self.route_id and not self.route.is_active and self.status == "ACTIVE":
            raise ValidationError({"route": f"Route {self.route.code} is inactive and cannot accept allocations."})
        if self.status == "ACTIVE" and self.student_id:
            existing = TransportAllocation.objects.filter(student=self.student, status="ACTIVE")
            if self.pk:
                existing = existing.exclude(pk=self.pk)
            if existing.exists():
                raise ValidationError({"student": "Student already has an active bus allocation."})
        if self.status == "ACTIVE" and self.vehicle_id:
            qs = TransportAllocation.objects.filter(vehicle=self.vehicle, status="ACTIVE")
            if self.pk:
                qs = qs.exclude(pk=self.pk)
            if qs.count() >= self.vehicle.seating_capacity:
                raise ValidationError({"vehicle": f"Vehicle {self.vehicle.vehicle_number} has reached maximum capacity of {self.vehicle.seating_capacity} seats."})


# ================================================================
# 8. TRANSPORT PASS
# ================================================================
class TransportPass(models.Model):
    STATUS_CHOICES = [
        ("ACTIVE", "Active"),
        ("EXPIRED", "Expired"),
        ("CANCELLED", "Cancelled"),
    ]

    pass_number = models.CharField(max_length=50, unique=True, default=generate_transport_pass_number)
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name="transport_passes")
    allocation = models.OneToOneField(TransportAllocation, on_delete=models.CASCADE, related_name="bus_pass")
    academic_year = models.CharField(max_length=20, default="2026-27")
    issue_date = models.DateField(default=timezone.now)
    expiry_date = models.DateField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="ACTIVE")
    barcode_data = models.CharField(max_length=100, blank=True)
    qr_code_token = models.CharField(max_length=100, blank=True)
    issued_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-issue_date"]
        verbose_name = "Transport Pass"
        verbose_name_plural = "Transport Passes"

    def __str__(self):
        return f"Pass {self.pass_number} - {self.student.name} ({self.status})"

    def clean(self):
        if self.expiry_date and self.issue_date and self.expiry_date < self.issue_date:
            raise ValidationError({"expiry_date": "Pass expiry date cannot be earlier than issue date."})

    @property
    def is_valid(self):
        return self.status == "ACTIVE" and self.expiry_date >= timezone.now().date()

    @property
    def is_expired(self):
        return self.expiry_date < timezone.now().date()


# ================================================================
# 9. TRANSPORT ATTENDANCE
# ================================================================
class TransportAttendance(models.Model):
    STATUS_CHOICES = [
        ("PRESENT", "Present / Boarded"),
        ("ABSENT", "Absent"),
        ("NOT_BOARDED", "Not Boarded"),
    ]

    TRIP_CHOICES = [
        ("MORNING", "Morning Pickup"),
        ("EVENING", "Evening Drop"),
    ]

    date = models.DateField(default=timezone.now)
    trip_type = models.CharField(max_length=20, choices=TRIP_CHOICES, default="MORNING")
    vehicle = models.ForeignKey(Vehicle, on_delete=models.CASCADE, related_name="attendance_records")
    route = models.ForeignKey(Route, on_delete=models.CASCADE, related_name="attendance_records")
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name="transport_attendance")
    boarding_stop = models.ForeignKey(Stop, on_delete=models.SET_NULL, null=True, blank=True)
    boarding_time = models.TimeField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="PRESENT")
    marked_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    remarks = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date", "route", "student"]
        verbose_name = "Transport Attendance"
        verbose_name_plural = "Transport Attendances"
        constraints = [
            models.UniqueConstraint(
                fields=["student", "date", "trip_type"],
                name="unique_transport_attendance_student_date_trip"
            )
        ]

    def __str__(self):
        return f"{self.date} [{self.trip_type}] - {self.student.name}: {self.status}"


# ================================================================
# 10. VEHICLE MAINTENANCE
# ================================================================
class VehicleMaintenance(models.Model):
    MAINTENANCE_TYPE_CHOICES = [
        ("REGULAR_SERVICE", "Regular Service"),
        ("REPAIR", "Repair"),
        ("TYRE", "Tyre"),
        ("ENGINE", "Engine Work"),
        ("ELECTRICAL", "Electrical"),
        ("INSURANCE", "Insurance Renewal"),
        ("FITNESS", "Fitness Certificate Inspection"),
        ("POLLUTION", "Pollution Certificate Test"),
        ("OTHER", "Other"),
    ]

    STATUS_CHOICES = [
        ("COMPLETED", "Completed"),
        ("SCHEDULED", "Scheduled"),
        ("IN_PROGRESS", "In Progress"),
        ("CANCELLED", "Cancelled"),
    ]

    vehicle = models.ForeignKey(Vehicle, on_delete=models.CASCADE, related_name="maintenance_records")
    maintenance_type = models.CharField(max_length=30, choices=MAINTENANCE_TYPE_CHOICES, default="REGULAR_SERVICE")
    service_date = models.DateField(default=timezone.now)
    next_service_date = models.DateField(null=True, blank=True)
    description = models.TextField()
    service_provider = models.CharField(max_length=150)
    cost = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"), validators=[MinValueValidator(Decimal("0.00"))])
    odometer_reading = models.PositiveIntegerField(null=True, blank=True)
    invoice_number = models.CharField(max_length=100, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="COMPLETED")
    remarks = models.TextField(blank=True)
    logged_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-service_date", "-created_at"]
        verbose_name = "Vehicle Maintenance"
        verbose_name_plural = "Vehicle Maintenances"

    def __str__(self):
        return f"{self.vehicle.vehicle_number} - {self.get_maintenance_type_display()} ({self.service_date})"

    def clean(self):
        if self.next_service_date and self.service_date and self.next_service_date < self.service_date:
            raise ValidationError({"next_service_date": "Next service date cannot precede the current service date."})

    @property
    def is_overdue(self):
        if not self.next_service_date or self.status == "COMPLETED":
            return False
        return self.next_service_date < timezone.now().date()


# ================================================================
# 11. TRANSPORT COMPLAINTS
# ================================================================
class TransportComplaint(models.Model):
    CATEGORY_CHOICES = [
        ("BUS_TIMING", "Bus Timing / Delay"),
        ("DRIVER_BEHAVIOR", "Driver / Staff Behavior"),
        ("RASH_DRIVING", "Rash / Unsafe Driving"),
        ("OVERCROWDING", "Overcrowding / Seating Issue"),
        ("CLEANLINESS", "Cleanliness / Hygiene"),
        ("BREAKDOWN", "Vehicle Breakdown"),
        ("ROUTE_ISSUE", "Route / Stop Alteration"),
        ("OTHER", "Other"),
    ]

    PRIORITY_CHOICES = [
        ("LOW", "Low"),
        ("MEDIUM", "Medium"),
        ("HIGH", "High"),
        ("CRITICAL", "Critical"),
    ]

    STATUS_CHOICES = [
        ("OPEN", "Open"),
        ("IN_PROGRESS", "In Progress"),
        ("RESOLVED", "Resolved"),
        ("CLOSED", "Closed"),
    ]

    complaint_id = models.CharField(max_length=50, unique=True, default=generate_transport_complaint_id)
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name="transport_complaints")
    route = models.ForeignKey(Route, on_delete=models.SET_NULL, null=True, blank=True, related_name="complaints")
    vehicle = models.ForeignKey(Vehicle, on_delete=models.SET_NULL, null=True, blank=True, related_name="complaints")
    category = models.CharField(max_length=30, choices=CATEGORY_CHOICES, default="BUS_TIMING")
    title = models.CharField(max_length=200)
    description = models.TextField()
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default="MEDIUM")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="OPEN")
    attachment = models.FileField(upload_to="transport/complaints/", blank=True, null=True)

    assigned_staff = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_transport_complaints"
    )
    resolution = models.TextField(blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Transport Complaint"
        verbose_name_plural = "Transport Complaints"

    def __str__(self):
        return f"{self.complaint_id} - {self.student.name}: {self.title} ({self.status})"


# ================================================================
# 12. TRANSPORT INCIDENTS
# ================================================================
class TransportIncident(models.Model):
    SEVERITY_CHOICES = [
        ("MINOR", "Minor"),
        ("MODERATE", "Moderate"),
        ("MAJOR", "Major"),
        ("CRITICAL", "Critical"),
    ]

    STATUS_CHOICES = [
        ("REPORTED", "Reported"),
        ("INVESTIGATING", "Investigating"),
        ("RESOLVED", "Resolved"),
    ]

    incident_id = models.CharField(max_length=50, unique=True, default=generate_transport_incident_id)
    date = models.DateField(default=timezone.now)
    vehicle = models.ForeignKey(Vehicle, on_delete=models.CASCADE, related_name="incidents")
    route = models.ForeignKey(Route, on_delete=models.SET_NULL, null=True, blank=True, related_name="incidents")
    description = models.TextField()
    severity = models.CharField(max_length=20, choices=SEVERITY_CHOICES, default="MINOR")
    action_taken = models.TextField(blank=True)
    reported_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="REPORTED")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-date", "-created_at"]
        verbose_name = "Transport Incident"
        verbose_name_plural = "Transport Incidents"

    def __str__(self):
        return f"{self.incident_id} - {self.vehicle.vehicle_number} ({self.date}): {self.severity}"
