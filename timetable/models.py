from django.db import models
from django.contrib.auth.models import User

from students.models import Department, Course
from faculty.models import Faculty, Subject


# ================================================================
# PERIOD
# The fixed hourly slots in a college day (e.g. 8 periods/hours).
# ================================================================

class Period(models.Model):

    period_number = models.PositiveIntegerField(
        unique=True
    )

    start_time = models.TimeField()
    end_time = models.TimeField()

    class Meta:
        ordering = ["period_number"]

    def __str__(self):
        return (
            f"Period {self.period_number} "
            f"({self.start_time.strftime('%I:%M %p')} - "
            f"{self.end_time.strftime('%I:%M %p')})"
        )


# ================================================================
# SCHOOL CLASS
# A specific batch of students that attends lessons together,
# e.g. "MCA - Year 1" or "B.Sc CS (AI & Data Science) - Year 2".
# ================================================================

class SchoolClass(models.Model):

    department = models.ForeignKey(
        Department,
        on_delete=models.CASCADE,
        related_name="classes"
    )

    course = models.ForeignKey(
        Course,
        on_delete=models.CASCADE,
        related_name="classes"
    )

    year = models.PositiveIntegerField()

    class Meta:
        unique_together = ("course", "year")

    def __str__(self):
        return f"{self.course.name} - Year {self.year}"

    @property
    def students(self):

        from students.models import Student

        return Student.objects.filter(
            course=self.course,
            year=self.year
        )


# ================================================================
# TIMETABLE
# One weekly lesson slot: on a given day + period, a SchoolClass
# is taught a Subject by a Faculty member.
# ================================================================

DAY_CHOICES = [
    ("MON", "Monday"),
    ("TUE", "Tuesday"),
    ("WED", "Wednesday"),
    ("THU", "Thursday"),
    ("FRI", "Friday"),
    ("SAT", "Saturday"),
]


class Timetable(models.Model):

    day_of_week = models.CharField(
        max_length=3,
        choices=DAY_CHOICES
    )

    period = models.ForeignKey(
        Period,
        on_delete=models.CASCADE
    )

    school_class = models.ForeignKey(
        SchoolClass,
        on_delete=models.CASCADE,
        related_name="timetable_slots"
    )

    subject = models.ForeignKey(
        Subject,
        on_delete=models.CASCADE
    )

    faculty = models.ForeignKey(
        Faculty,
        on_delete=models.CASCADE,
        related_name="timetable_slots"
    )

    class Meta:
        constraints = [

            # A class can only have one lesson per day+period.
            models.UniqueConstraint(
                fields=["day_of_week", "period", "school_class"],
                name="unique_class_slot"
            ),

            # A faculty member can't be in two places at once.
            models.UniqueConstraint(
                fields=["day_of_week", "period", "faculty"],
                name="unique_faculty_slot"
            ),
        ]

        ordering = ["day_of_week", "period__period_number"]

    def __str__(self):
        return (
            f"{self.get_day_of_week_display()} "
            f"P{self.period.period_number} - "
            f"{self.school_class} - "
            f"{self.subject.name} "
            f"({self.faculty.name})"
        )


# ================================================================
# SCHOOL INCHARGE
# One Faculty member designated in charge of a School (Department).
# ================================================================

class SchoolIncharge(models.Model):

    department = models.OneToOneField(
        Department,
        on_delete=models.CASCADE,
        related_name="incharge"
    )

    faculty = models.OneToOneField(
        Faculty,
        on_delete=models.CASCADE,
        related_name="incharge_of"
    )

    def __str__(self):
        return f"{self.faculty.name} — Incharge of {self.department.name}"


# ================================================================
# CIRCULAR
# An announcement the admin posts for everyone (or a specific
# audience) to see.
# ================================================================

AUDIENCE_CHOICES = [
    ("ALL", "Everyone"),
    ("STUDENT", "Students Only"),
    ("FACULTY", "Faculty Only"),
]


class Notification(models.Model):
    recipient = models.ForeignKey(User, on_delete=models.CASCADE, related_name="smartcollege_notifications")
    title = models.CharField(max_length=200)
    message = models.TextField()
    link = models.CharField(max_length=300, blank=True)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.recipient.username}: {self.title}"


class Exam(models.Model):
    EXAM_TYPE_CHOICES = [
        ("CAT1", "CAT 1"),
        ("CAT2", "CAT 2"),
        ("CAT3", "CAT 3"),
        ("SEM", "Semester Exam"),
        ("PRACTICAL", "Practical Exam"),
    ]
    name = models.CharField(max_length=100)
    exam_type = models.CharField(max_length=20, choices=EXAM_TYPE_CHOICES)
    school_class = models.ForeignKey(SchoolClass, on_delete=models.CASCADE, related_name="exams")
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name="exams")
    exam_date = models.DateField()
    start_time = models.TimeField()
    end_time = models.TimeField()
    room = models.CharField(max_length=50, blank=True)
    invigilator = models.ForeignKey(Faculty, on_delete=models.SET_NULL, null=True, blank=True, related_name="invigilated_exams")
    max_marks = models.PositiveIntegerField(default=100)
    published = models.BooleanField(default=False)

    class Meta:
        ordering = ["exam_date", "start_time"]

    def __str__(self):
        return f"{self.name} - {self.school_class} - {self.subject.name}"


class Circular(models.Model):

    title = models.CharField(max_length=200)
    message = models.TextField()

    audience = models.CharField(
        max_length=10,
        choices=AUDIENCE_CHOICES,
        default="ALL"
    )
    target_department = models.ForeignKey(Department, on_delete=models.SET_NULL, null=True, blank=True, related_name="target_circulars")
    target_course = models.ForeignKey(Course, on_delete=models.SET_NULL, null=True, blank=True, related_name="target_circulars")
    target_year = models.PositiveIntegerField(null=True, blank=True)

    posted_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True
    )

    posted_at = models.DateTimeField(
        auto_now_add=True
    )

    class Meta:
        ordering = ["-posted_at"]

    def __str__(self):
        return self.title


# ================================================================
# FACULTY LEAVE REQUEST
# Faculty -> School Incharge -> Admin workflow.
# ================================================================

LEAVE_STATUS_CHOICES = [
    ("PENDING", "Pending"),
    ("APPROVED", "Approved by School Incharge"),
    ("REJECTED", "Rejected by School Incharge"),
]


class FacultyLeaveRequest(models.Model):
    faculty = models.ForeignKey(
        Faculty,
        on_delete=models.CASCADE,
        related_name="leave_requests",
    )
    department = models.ForeignKey(
        Department,
        on_delete=models.CASCADE,
        related_name="faculty_leave_requests",
    )
    LEAVE_TYPE_CHOICES = [
        ("CASUAL", "Casual Leave"),
        ("MEDICAL", "Medical Leave"),
        ("OD", "On Duty"),
        ("EMERGENCY", "Emergency Leave"),
    ]
    leave_type = models.CharField(max_length=20, choices=LEAVE_TYPE_CHOICES, default="CASUAL")
    from_date = models.DateField()
    to_date = models.DateField()
    reason = models.TextField()
    supporting_document = models.FileField(upload_to="leave_documents/", blank=True, null=True)
    status = models.CharField(
        max_length=20,
        choices=LEAVE_STATUS_CHOICES,
        default="PENDING",
    )
    incharge_comment = models.TextField(blank=True)
    reviewed_by = models.ForeignKey(
        Faculty,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reviewed_leave_requests",
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    forwarded_to_admin = models.BooleanField(default=False)
    admin_seen = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.faculty.name} - {self.from_date} to {self.to_date}"
