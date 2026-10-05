import os
from datetime import date
from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils import timezone


def validate_leave_document(value):
    """
    Validate that supporting document is a PDF, JPG, or PNG and under 15MB.
    """
    ext = os.path.splitext(value.name)[1].lower()
    valid_extensions = [".pdf", ".jpg", ".jpeg", ".png"]
    if ext not in valid_extensions:
        raise ValidationError(f"Unsupported file format '{ext}'. Allowed formats: PDF, JPG, JPEG, PNG.")

    max_size = 15 * 1024 * 1024  # 15 MB
    if value.size > max_size:
        raise ValidationError(f"File size exceeds the 15MB limit ({value.size / (1024 * 1024):.1f}MB).")


class StudentLeaveRequest(models.Model):
    # Leave Types
    TYPE_SICK = "Sick Leave"
    TYPE_EMERGENCY = "Emergency Leave"
    TYPE_PERSONAL = "Personal Leave"
    TYPE_FAMILY = "Family Function"
    TYPE_MEDICAL = "Medical Leave"
    TYPE_OTHER = "Other"

    LEAVE_TYPE_CHOICES = [
        (TYPE_SICK, "Sick Leave"),
        (TYPE_EMERGENCY, "Emergency Leave"),
        (TYPE_PERSONAL, "Personal Leave"),
        (TYPE_FAMILY, "Family Function"),
        (TYPE_MEDICAL, "Medical Leave"),
        (TYPE_OTHER, "Other"),
    ]

    # Leave Statuses
    STATUS_PENDING = "Pending"
    STATUS_FACULTY_APPROVED = "Faculty Approved"
    STATUS_FACULTY_REJECTED = "Faculty Rejected"
    STATUS_INCHARGE_APPROVED = "Incharge Approved"
    STATUS_INCHARGE_REJECTED = "Incharge Rejected"
    STATUS_ADMIN_APPROVED = "Admin Approved"
    STATUS_ADMIN_REJECTED = "Admin Rejected"
    STATUS_CANCELLED = "Cancelled"

    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_FACULTY_APPROVED, "Faculty Approved"),
        (STATUS_FACULTY_REJECTED, "Faculty Rejected"),
        (STATUS_INCHARGE_APPROVED, "Incharge Approved"),
        (STATUS_INCHARGE_REJECTED, "Incharge Rejected"),
        (STATUS_ADMIN_APPROVED, "Admin Approved"),
        (STATUS_ADMIN_REJECTED, "Admin Rejected"),
        (STATUS_CANCELLED, "Cancelled"),
    ]

    student = models.ForeignKey(
        "students.Student",
        on_delete=models.CASCADE,
        related_name="leave_requests",
    )
    leave_type = models.CharField(
        max_length=50,
        choices=LEAVE_TYPE_CHOICES,
        default=TYPE_SICK,
    )
    from_date = models.DateField()
    to_date = models.DateField()
    number_of_days = models.PositiveIntegerField(default=1)
    reason = models.TextField()
    supporting_document = models.FileField(
        upload_to="student_leaves/",
        blank=True,
        null=True,
        validators=[validate_leave_document],
    )
    applied_date = models.DateTimeField(auto_now_add=True)
    status = models.CharField(
        max_length=50,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING,
    )

    # Multi-tier remarks
    student_remarks = models.TextField(blank=True)
    faculty_remarks = models.TextField(blank=True)
    incharge_remarks = models.TextField(blank=True)
    admin_remarks = models.TextField(blank=True)

    # Final or latest decision audit
    approved_rejected_date = models.DateTimeField(null=True, blank=True)
    approved_rejected_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="approved_student_leaves",
    )

    created_date = models.DateTimeField(auto_now_add=True)
    updated_date = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-applied_date"]
        verbose_name = "Student Leave Request"
        verbose_name_plural = "Student Leave Requests"

    def __str__(self):
        return f"{self.student.name} ({self.student.roll_no}) - {self.leave_type} ({self.from_date} to {self.to_date})"

    def clean(self):
        super().clean()
        if self.from_date and self.to_date:
            if self.from_date > self.to_date:
                raise ValidationError({"from_date": "From date cannot be after To date."})

            today = timezone.localdate() if hasattr(timezone, "localdate") else date.today()
            if self.from_date < today:
                allowed_retroactive = [self.TYPE_SICK, self.TYPE_MEDICAL, self.TYPE_EMERGENCY]
                if self.leave_type not in allowed_retroactive:
                    raise ValidationError({
                        "from_date": "Past-date leave application is only allowed for Medical, Sick, or Emergency leaves."
                    })
                delta = (today - self.from_date).days
                if delta > 7:
                    raise ValidationError({
                        "from_date": "Past-date leave applications cannot exceed 7 days prior to today."
                    })

            # Check for overlapping leave requests for the same student
            if self.student_id:
                inactive_statuses = [
                    self.STATUS_CANCELLED,
                    self.STATUS_FACULTY_REJECTED,
                    self.STATUS_INCHARGE_REJECTED,
                    self.STATUS_ADMIN_REJECTED,
                ]
                overlap_qs = StudentLeaveRequest.objects.filter(
                    student_id=self.student_id,
                    from_date__lte=self.to_date,
                    to_date__gte=self.from_date,
                ).exclude(status__in=inactive_statuses)

                if self.pk:
                    overlap_qs = overlap_qs.exclude(pk=self.pk)

                if overlap_qs.exists():
                    existing = overlap_qs.first()
                    raise ValidationError(
                        f"An active leave request ({existing.from_date} to {existing.to_date}, Status: {existing.status}) already overlaps with these dates."
                    )

    def save(self, *args, **kwargs):
        if self.from_date and self.to_date and self.to_date >= self.from_date:
            self.number_of_days = (self.to_date - self.from_date).days + 1
        super().save(*args, **kwargs)

    @property
    def is_final_decision(self):
        return self.status in [
            self.STATUS_ADMIN_APPROVED,
            self.STATUS_ADMIN_REJECTED,
            self.STATUS_FACULTY_REJECTED,
            self.STATUS_INCHARGE_REJECTED,
            self.STATUS_CANCELLED,
        ]

    @property
    def can_student_cancel(self):
        return self.status == self.STATUS_PENDING

    @property
    def status_badge_class(self):
        if self.status == self.STATUS_ADMIN_APPROVED:
            return "green"
        elif self.status in [self.STATUS_PENDING, self.STATUS_FACULTY_APPROVED, self.STATUS_INCHARGE_APPROVED]:
            return "amber"
        elif "Rejected" in self.status:
            return "red"
        elif self.status == self.STATUS_CANCELLED:
            return "gray"
        return "brand"


class StudentLeaveHistory(models.Model):
    """
    Immutable audit history log recording every action and state transition
    on a StudentLeaveRequest.
    """
    leave_request = models.ForeignKey(
        StudentLeaveRequest,
        on_delete=models.CASCADE,
        related_name="history",
    )
    action = models.CharField(max_length=100)
    previous_status = models.CharField(max_length=50, blank=True)
    new_status = models.CharField(max_length=50)
    action_taken_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="leave_history_actions",
    )
    remarks = models.TextField(blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["timestamp"]
        verbose_name = "Student Leave History"
        verbose_name_plural = "Student Leave Histories"

    def __str__(self):
        return f"{self.leave_request.id} - {self.action} ({self.new_status}) at {self.timestamp}"
