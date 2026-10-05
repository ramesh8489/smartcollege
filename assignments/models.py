from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.core.exceptions import ValidationError
import os

from students.models import Student, Course
from faculty.models import Faculty, Subject


def validate_file_size(value):
    # 15 MB limit
    max_size = 15 * 1024 * 1024
    if value.size > max_size:
        raise ValidationError(f"File size exceeds maximum permitted limit of 15MB (uploaded: {round(value.size / (1024 * 1024), 1)}MB).")


def validate_allowed_file_extension(value):
    ext = os.path.splitext(value.name)[1].lower()
    valid_extensions = [
        ".pdf", ".doc", ".docx", ".zip", ".rar", ".7z",
        ".txt", ".py", ".ipynb", ".jpg", ".jpeg", ".png",
        ".ppt", ".pptx", ".xls", ".xlsx", ".csv",
    ]
    if ext not in valid_extensions:
        raise ValidationError(f"Unsupported file format '{ext}'. Allowed formats: {', '.join(valid_extensions)}")


class Assignment(models.Model):
    """
    Academic assignment, project, homework, or coursework created by faculty.
    """
    ASSIGNMENT_TYPE_CHOICES = [
        ("Assignment", "Assignment"),
        ("Homework", "Homework"),
        ("Project", "Project"),
        ("Lab Record", "Lab Record"),
        ("Seminar", "Seminar"),
        ("Case Study", "Case Study"),
    ]

    YEAR_CHOICES = [
        (1, "1st Year"),
        (2, "2nd Year"),
        (3, "3rd Year"),
        (4, "4th Year"),
    ]

    SEMESTER_CHOICES = [
        (1, "Semester 1"),
        (2, "Semester 2"),
        (3, "Semester 3"),
        (4, "Semester 4"),
        (5, "Semester 5"),
        (6, "Semester 6"),
        (7, "Semester 7"),
        (8, "Semester 8"),
    ]

    title = models.CharField(max_length=200, verbose_name="Assignment Title")
    description = models.TextField(blank=True, verbose_name="Description")
    faculty = models.ForeignKey(
        Faculty,
        on_delete=models.CASCADE,
        related_name="created_assignments",
        verbose_name="Faculty"
    )
    subject = models.ForeignKey(
        Subject,
        on_delete=models.CASCADE,
        related_name="assignments",
        verbose_name="Subject"
    )
    course = models.ForeignKey(
        Course,
        on_delete=models.CASCADE,
        related_name="assignments",
        verbose_name="Course/Degree"
    )
    year = models.PositiveSmallIntegerField(choices=YEAR_CHOICES, verbose_name="Year")
    semester = models.PositiveSmallIntegerField(choices=SEMESTER_CHOICES, verbose_name="Semester")
    academic_year = models.CharField(max_length=20, default="2026-2027", verbose_name="Academic Year")
    assignment_type = models.CharField(
        max_length=50,
        choices=ASSIGNMENT_TYPE_CHOICES,
        default="Assignment",
        verbose_name="Assignment Type"
    )

    assigned_date = models.DateField(default=timezone.localdate, verbose_name="Assigned Date")
    submission_deadline = models.DateTimeField(verbose_name="Submission Deadline")
    max_marks = models.PositiveIntegerField(default=100, verbose_name="Maximum Marks")
    attachment = models.FileField(
        upload_to="assignments/materials/%Y/%m/",
        blank=True,
        null=True,
        validators=[validate_file_size, validate_allowed_file_extension],
        verbose_name="Attachment / Material File"
    )
    instructions = models.TextField(blank=True, verbose_name="Instructions")
    is_active = models.BooleanField(default=True, verbose_name="Active Status")

    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Created Date")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Updated Date")

    class Meta:
        ordering = ["-submission_deadline", "-created_at"]
        verbose_name = "Assignment"
        verbose_name_plural = "Assignments"

    def __str__(self):
        return f"{self.title} ({self.subject.name}) - {self.course.name} Yr {self.year}"

    def clean(self):
        super().clean()
        if self.assigned_date and self.submission_deadline:
            deadline_date = self.submission_deadline.date()
            if deadline_date < self.assigned_date:
                raise ValidationError({
                    "submission_deadline": f"Submission deadline ({deadline_date}) cannot be earlier than assigned date ({self.assigned_date})."
                })

    @property
    def is_deadline_passed(self):
        return timezone.now() > self.submission_deadline

    @property
    def time_remaining_display(self):
        now = timezone.now()
        if now > self.submission_deadline:
            diff = now - self.submission_deadline
            days = diff.days
            hours = diff.seconds // 3600
            if days > 0:
                return f"Closed ({days}d ago)"
            return f"Closed ({hours}h ago)"
        else:
            diff = self.submission_deadline - now
            days = diff.days
            hours = diff.seconds // 3600
            if days > 0:
                return f"{days} days remaining"
            elif hours > 0:
                return f"{hours} hours remaining"
            else:
                mins = diff.seconds // 60
                return f"{mins} mins remaining"

    @property
    def submission_count(self):
        return self.submissions.count()

    @property
    def pending_evaluation_count(self):
        return self.submissions.filter(status__in=["Submitted", "Late"]).count()

    @property
    def evaluated_count(self):
        return self.submissions.filter(status="Evaluated").count()


class AssignmentSubmission(models.Model):
    """
    Student submission for an assignment, along with grading and feedback.
    """
    SUBMISSION_STATUS_CHOICES = [
        ("Not Submitted", "Not Submitted"),
        ("Submitted", "Submitted"),
        ("Late", "Late"),
        ("Evaluated", "Evaluated"),
        ("Returned", "Returned"),
    ]

    assignment = models.ForeignKey(
        Assignment,
        on_delete=models.CASCADE,
        related_name="submissions",
        verbose_name="Assignment"
    )
    student = models.ForeignKey(
        Student,
        on_delete=models.CASCADE,
        related_name="assignment_submissions",
        verbose_name="Student"
    )
    submission_file = models.FileField(
        upload_to="assignments/submissions/%Y/%m/",
        validators=[validate_file_size, validate_allowed_file_extension],
        verbose_name="Submission File"
    )
    student_remarks = models.TextField(blank=True, verbose_name="Student Remarks")
    submitted_at = models.DateTimeField(auto_now_add=True, verbose_name="Submitted At")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Updated At")

    status = models.CharField(
        max_length=30,
        choices=SUBMISSION_STATUS_CHOICES,
        default="Submitted",
        verbose_name="Submission Status"
    )

    # Evaluation fields:
    marks_obtained = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Marks Obtained"
    )
    percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Percentage"
    )
    feedback = models.TextField(blank=True, verbose_name="Faculty Feedback")
    evaluated_at = models.DateTimeField(null=True, blank=True, verbose_name="Evaluation Date")
    evaluated_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="evaluated_submissions",
        verbose_name="Evaluated By"
    )

    class Meta:
        ordering = ["-submitted_at"]
        verbose_name = "Assignment Submission"
        verbose_name_plural = "Assignment Submissions"
        constraints = [
            models.UniqueConstraint(
                fields=["assignment", "student"],
                name="unique_assignment_student_submission"
            )
        ]

    def __str__(self):
        return f"{self.student.name} - {self.assignment.title} ({self.status})"

    def clean(self):
        super().clean()
        if self.marks_obtained is not None:
            if self.marks_obtained < 0:
                raise ValidationError({"marks_obtained": "Marks obtained cannot be negative."})
            if self.assignment and self.marks_obtained > self.assignment.max_marks:
                raise ValidationError({
                    "marks_obtained": f"Marks obtained ({self.marks_obtained}) cannot exceed maximum marks ({self.assignment.max_marks})."
                })

    def save(self, *args, **kwargs):
        # 1. Validation check
        if self.marks_obtained is not None:
            if self.marks_obtained < 0:
                raise ValidationError("Marks obtained cannot be negative.")
            if self.assignment and self.marks_obtained > self.assignment.max_marks:
                raise ValidationError(f"Marks obtained ({self.marks_obtained}) cannot exceed maximum marks ({self.assignment.max_marks}).")

        # 2. Check if marks are provided -> set Evaluated
        if self.marks_obtained is not None and self.assignment and self.assignment.max_marks > 0:
            self.percentage = round((float(self.marks_obtained) / float(self.assignment.max_marks)) * 100, 2)
            if self.status != "Returned":
                self.status = "Evaluated"
            if not self.evaluated_at:
                self.evaluated_at = timezone.now()
        else:
            # Automatic status based on deadline if not yet evaluated or returned
            if self.status not in ["Evaluated", "Returned"]:
                now = timezone.now()
                if self.assignment and now > self.assignment.submission_deadline:
                    self.status = "Late"
                else:
                    self.status = "Submitted"

        super().save(*args, **kwargs)

    @property
    def file_extension(self):
        if self.submission_file:
            return os.path.splitext(self.submission_file.name)[1].lower().replace(".", "")
        return ""

    @property
    def file_basename(self):
        if self.submission_file:
            return os.path.basename(self.submission_file.name)
        return ""

    @property
    def is_late(self):
        return self.status == "Late" or (bool(self.submitted_at) and bool(self.assignment) and self.submitted_at > self.assignment.submission_deadline)

    @property
    def badge_class(self):
        if self.status == "Evaluated":
            return "green"
        elif self.status == "Submitted":
            return "violet"
        elif self.status == "Late":
            return "amber"
        elif self.status == "Returned":
            return "rose"
        return ""
