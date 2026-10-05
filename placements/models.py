import os
from decimal import Decimal
from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils import timezone


def validate_resume_file(value):
    """
    Validate that uploaded resumes or offer letters are PDF, DOC, or DOCX and <= 15MB.
    """
    ext = os.path.splitext(value.name)[1].lower()
    valid_extensions = [".pdf", ".doc", ".docx"]
    if ext not in valid_extensions:
        raise ValidationError(f"Unsupported file format '{ext}'. Allowed formats: PDF, DOC, DOCX.")

    max_size = 15 * 1024 * 1024  # 15 MB
    if value.size > max_size:
        raise ValidationError(f"File size exceeds the 15MB limit ({value.size / (1024 * 1024):.1f}MB).")


class Company(models.Model):
    STATUS_ACTIVE = "Active"
    STATUS_INACTIVE = "Inactive"
    STATUS_CHOICES = [
        (STATUS_ACTIVE, "Active"),
        (STATUS_INACTIVE, "Inactive"),
    ]

    name = models.CharField(max_length=200, unique=True)
    logo = models.ImageField(upload_to="company_logos/", blank=True, null=True)
    industry = models.CharField(max_length=100)
    website = models.URLField(blank=True)
    hr_contact_person = models.CharField(max_length=150, blank=True)
    contact_email = models.EmailField(blank=True)
    contact_phone = models.CharField(max_length=30, blank=True)
    address = models.TextField(blank=True)
    description = models.TextField(blank=True)
    minimum_qualification = models.CharField(max_length=150, blank=True, default="B.Tech / MCA / Any Graduate")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_ACTIVE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "Company"
        verbose_name_plural = "Companies"

    def __str__(self):
        return f"{self.name} ({self.industry})"

    @property
    def is_active(self):
        return self.status == self.STATUS_ACTIVE


class PlacementDrive(models.Model):
    # Employment Types
    TYPE_FULL_TIME = "Full Time"
    TYPE_INTERNSHIP = "Internship"
    TYPE_INTERN_FT = "Internship + Full Time"
    TYPE_PART_TIME = "Part Time"
    TYPE_CONTRACT = "Contract"
    EMPLOYMENT_CHOICES = [
        (TYPE_FULL_TIME, "Full Time"),
        (TYPE_INTERNSHIP, "Internship"),
        (TYPE_INTERN_FT, "Internship + Full Time"),
        (TYPE_PART_TIME, "Part Time"),
        (TYPE_CONTRACT, "Contract"),
    ]

    # Drive Status
    STATUS_DRAFT = "Draft"
    STATUS_OPEN = "Open"
    STATUS_CLOSED = "Closed"
    STATUS_COMPLETED = "Completed"
    STATUS_CANCELLED = "Cancelled"
    STATUS_CHOICES = [
        (STATUS_DRAFT, "Draft"),
        (STATUS_OPEN, "Open"),
        (STATUS_CLOSED, "Closed"),
        (STATUS_COMPLETED, "Completed"),
        (STATUS_CANCELLED, "Cancelled"),
    ]

    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="drives")
    job_title = models.CharField(max_length=200)
    job_description = models.TextField()
    employment_type = models.CharField(max_length=50, choices=EMPLOYMENT_CHOICES, default=TYPE_FULL_TIME)
    job_location = models.CharField(max_length=150, default="Pan India")
    salary_package = models.CharField(max_length=100, help_text="e.g. 7.5 LPA, 12 LPA, 25,000/month")
    salary_lpa = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True, help_text="Numeric CTC in LPA for sorting/stats")

    # Eligibility Criteria
    minimum_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=60.00, help_text="Minimum academic percentage required")
    maximum_backlogs = models.PositiveIntegerField(default=0, help_text="Maximum standing backlogs allowed")
    minimum_qualification = models.CharField(max_length=150, blank=True, default="B.Tech / MCA")
    eligible_departments = models.ManyToManyField(
        "students.Department",
        blank=True,
        related_name="placement_drives",
        help_text="Eligible schools/departments (leave empty for all)",
    )
    eligible_courses = models.ManyToManyField(
        "students.Course",
        blank=True,
        related_name="placement_drives",
        help_text="Eligible courses/degrees (leave empty for all)",
    )
    eligible_year = models.PositiveIntegerField(
        default=4,
        help_text="Target graduating year (e.g. 3 or 4). Use 0 for all years.",
    )

    # Schedule & Details
    application_start_date = models.DateField(default=timezone.now)
    application_deadline = models.DateField()
    drive_date = models.DateField()
    drive_location = models.CharField(max_length=200, default="Campus / Virtual")
    vacancies_count = models.PositiveIntegerField(default=5)
    selection_process = models.TextField(default="Aptitude Test -> Technical Interview -> HR Round")
    description = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_OPEN)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-drive_date", "-created_at"]
        verbose_name = "Placement Drive"
        verbose_name_plural = "Placement Drives"

    def __str__(self):
        return f"{self.company.name} - {self.job_title} ({self.salary_package})"

    def clean(self):
        super().clean()
        if self.application_start_date and self.application_deadline:
            if self.application_start_date > self.application_deadline:
                raise ValidationError({"application_deadline": "Application deadline cannot be before start date."})

    @property
    def is_open(self):
        today = timezone.localdate()
        return self.status == self.STATUS_OPEN and self.application_deadline >= today

    @property
    def is_upcoming(self):
        today = timezone.localdate()
        return self.drive_date >= today

    @property
    def status_badge_class(self):
        if self.status == self.STATUS_OPEN:
            return "green"
        elif self.status == self.STATUS_CLOSED:
            return "amber"
        elif self.status == self.STATUS_COMPLETED:
            return "violet"
        elif self.status == self.STATUS_CANCELLED:
            return "red"
        return "gray"


class StudentPlacementProfile(models.Model):
    """
    Dedicated profile linking a Student with their placement preferences,
    default uploaded resume, and professional links.
    """
    student = models.OneToOneField(
        "students.Student",
        on_delete=models.CASCADE,
        related_name="placement_profile",
    )
    default_resume = models.FileField(
        upload_to="placement_resumes/",
        blank=True,
        null=True,
        validators=[validate_resume_file],
    )
    linkedin_url = models.URLField(blank=True)
    github_url = models.URLField(blank=True)
    portfolio_url = models.URLField(blank=True)
    skills = models.CharField(max_length=300, blank=True, help_text="Comma-separated skills e.g. Python, SQL, React")
    bio = models.TextField(blank=True)
    cgpa_or_percentage = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    active_backlogs = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Placement Profile - {self.student.name} ({self.student.roll_no})"


class PlacementApplication(models.Model):
    STATUS_APPLIED = "Applied"
    STATUS_SHORTLISTED = "Shortlisted"
    STATUS_REJECTED = "Rejected"
    STATUS_INTERVIEW = "Interview Scheduled"
    STATUS_SELECTED = "Selected"
    STATUS_NOT_SELECTED = "Not Selected"
    STATUS_WITHDRAWN = "Withdrawn"

    STATUS_CHOICES = [
        (STATUS_APPLIED, "Applied"),
        (STATUS_SHORTLISTED, "Shortlisted"),
        (STATUS_REJECTED, "Rejected"),
        (STATUS_INTERVIEW, "Interview Scheduled"),
        (STATUS_SELECTED, "Selected"),
        (STATUS_NOT_SELECTED, "Not Selected"),
        (STATUS_WITHDRAWN, "Withdrawn"),
    ]

    student = models.ForeignKey(
        "students.Student",
        on_delete=models.CASCADE,
        related_name="placement_applications",
    )
    placement_drive = models.ForeignKey(
        PlacementDrive,
        on_delete=models.CASCADE,
        related_name="applications",
    )
    application_date = models.DateTimeField(auto_now_add=True)
    resume = models.FileField(upload_to="placement_resumes/", validators=[validate_resume_file])
    cover_letter = models.TextField(blank=True)
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default=STATUS_APPLIED)
    eligibility_status = models.BooleanField(default=True)
    current_round = models.CharField(max_length=100, default="Application Review")
    remarks = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-application_date"]
        unique_together = ("student", "placement_drive")
        verbose_name = "Placement Application"
        verbose_name_plural = "Placement Applications"

    def __str__(self):
        return f"{self.student.name} - {self.placement_drive.company.name} ({self.status})"

    @property
    def status_badge_class(self):
        if self.status == self.STATUS_SELECTED:
            return "green"
        elif self.status in [self.STATUS_SHORTLISTED, self.STATUS_INTERVIEW]:
            return "amber"
        elif self.status in [self.STATUS_REJECTED, self.STATUS_NOT_SELECTED]:
            return "red"
        elif self.status == self.STATUS_WITHDRAWN:
            return "gray"
        return "brand"


class PlacementRound(models.Model):
    ROUND_TYPES = [
        ("Aptitude", "Aptitude Test"),
        ("Technical Test", "Technical Test"),
        ("Coding", "Coding Test"),
        ("Group Discussion", "Group Discussion"),
        ("Technical Interview", "Technical Interview"),
        ("HR Interview", "HR Interview"),
        ("Final Interview", "Final Interview"),
        ("Other", "Other"),
    ]

    RESULT_PENDING = "Pending"
    RESULT_PASSED = "Passed"
    RESULT_FAILED = "Failed"
    RESULT_SELECTED = "Selected"
    RESULT_CHOICES = [
        (RESULT_PENDING, "Pending"),
        (RESULT_PASSED, "Passed"),
        (RESULT_FAILED, "Failed"),
        (RESULT_SELECTED, "Selected"),
    ]

    application = models.ForeignKey(
        PlacementApplication,
        on_delete=models.CASCADE,
        related_name="rounds",
    )
    round_number = models.PositiveIntegerField(default=1)
    round_name = models.CharField(max_length=100)
    round_type = models.CharField(max_length=50, choices=ROUND_TYPES, default="Technical Interview")
    scheduled_date = models.DateField()
    start_time = models.TimeField()
    end_time = models.TimeField(null=True, blank=True)
    location = models.CharField(max_length=200, default="Room 302 / Online Meet")
    interviewer = models.CharField(max_length=150, blank=True)
    result = models.CharField(max_length=20, choices=RESULT_CHOICES, default=RESULT_PENDING)
    score = models.CharField(max_length=50, blank=True)
    remarks = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["round_number", "scheduled_date", "start_time"]
        verbose_name = "Placement Round"
        verbose_name_plural = "Placement Rounds"

    def __str__(self):
        return f"Round {self.round_number}: {self.round_name} - {self.application.student.name} ({self.result})"

    @property
    def result_badge_class(self):
        if self.result in [self.RESULT_PASSED, self.RESULT_SELECTED]:
            return "green"
        elif self.result == self.RESULT_PENDING:
            return "amber"
        elif self.result == self.RESULT_FAILED:
            return "red"
        return "gray"


class PlacementResult(models.Model):
    RESULT_SELECTED = "Selected"
    RESULT_NOT_SELECTED = "Not Selected"
    RESULT_CHOICES = [
        (RESULT_SELECTED, "Selected"),
        (RESULT_NOT_SELECTED, "Not Selected"),
    ]

    TYPE_FULL_TIME = "Full Time"
    TYPE_INTERNSHIP = "Internship"
    TYPE_INTERN_FT = "Internship + Full Time"
    TYPE_CHOICES = [
        (TYPE_FULL_TIME, "Full Time"),
        (TYPE_INTERNSHIP, "Internship"),
        (TYPE_INTERN_FT, "Internship + Full Time"),
    ]

    student = models.ForeignKey(
        "students.Student",
        on_delete=models.CASCADE,
        related_name="placement_results",
    )
    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name="placement_results",
    )
    placement_drive = models.ForeignKey(
        PlacementDrive,
        on_delete=models.CASCADE,
        related_name="placement_results",
    )
    job_title = models.CharField(max_length=200)
    ctc = models.CharField(max_length=100)
    joining_date = models.DateField(null=True, blank=True)
    placement_type = models.CharField(max_length=50, choices=TYPE_CHOICES, default=TYPE_FULL_TIME)
    offer_letter = models.FileField(upload_to="placement_offers/", blank=True, null=True, validators=[validate_resume_file])
    result = models.CharField(max_length=30, choices=RESULT_CHOICES, default=RESULT_SELECTED)
    result_date = models.DateField(default=timezone.now)
    remarks = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-result_date"]
        verbose_name = "Placement Result"
        verbose_name_plural = "Placement Results"

    def __str__(self):
        return f"{self.student.name} - {self.company.name} ({self.result}) CTC: {self.ctc}"
