from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.core.exceptions import ValidationError

from students.models import Student, Course
from faculty.models import Subject, Faculty


def compute_grade_and_points(percentage, is_absent=False):
    """
    Standard grading system:
    >= 90%: Grade O (Outstanding), GP 10.0, Pass
    >= 80%: Grade A+ (Excellent), GP 9.0, Pass
    >= 70%: Grade A (Very Good), GP 8.0, Pass
    >= 60%: Grade B+ (Good), GP 7.0, Pass
    >= 50%: Grade B (Above Average), GP 6.0, Pass
    >= 40%: Grade C (Average / Pass), GP 5.0, Pass
    < 40%:  Grade F (Fail), GP 0.0, Fail
    Absent: Grade AB, GP 0.0, Fail
    """
    if is_absent:
        return "AB", 0.0, "Fail"
    pct = float(percentage)
    if pct >= 90.0:
        return "O", 10.0, "Pass"
    elif pct >= 80.0:
        return "A+", 9.0, "Pass"
    elif pct >= 70.0:
        return "A", 8.0, "Pass"
    elif pct >= 60.0:
        return "B+", 7.0, "Pass"
    elif pct >= 50.0:
        return "B", 6.0, "Pass"
    elif pct >= 40.0:
        return "C", 5.0, "Pass"
    else:
        return "F", 0.0, "Fail"


class Exam(models.Model):
    """
    Exam Management model representing an examination event/session.
    """
    EXAM_TYPE_CHOICES = [
        ("CAT 1", "CAT 1"),
        ("CAT 2", "CAT 2"),
        ("CAT 3", "CAT 3"),
        ("Model Exam", "Model Exam"),
        ("Semester Exam", "Semester Exam"),
        ("Internal Exam", "Internal Exam"),
        ("Practical Exam", "Practical Exam"),
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

    # Required fields as specified by user:
    name = models.CharField(max_length=150, verbose_name="Exam Name")
    exam_type = models.CharField(max_length=50, choices=EXAM_TYPE_CHOICES, verbose_name="Exam Type")
    academic_year = models.CharField(max_length=20, default="2026-2027", verbose_name="Academic Year")
    semester = models.PositiveSmallIntegerField(choices=SEMESTER_CHOICES, verbose_name="Semester")
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name="managed_exams", verbose_name="Course/Degree")
    year = models.PositiveSmallIntegerField(choices=YEAR_CHOICES, verbose_name="Year")
    start_date = models.DateField(verbose_name="Start Date")
    end_date = models.DateField(verbose_name="End Date")
    description = models.TextField(blank=True, verbose_name="Description")
    is_active = models.BooleanField(default=True, verbose_name="Active Status")

    # Audit fields:
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="created_exams")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-start_date", "-created_at"]
        verbose_name = "Exam"
        verbose_name_plural = "Exams"

    def __str__(self):
        return f"{self.name} ({self.exam_type}) - {self.course.name} Yr {self.year} Sem {self.semester}"

    @property
    def timeline_status(self):
        """Returns the timeline status of the exam (Upcoming, Ongoing, Completed, or Inactive)."""
        if not self.is_active:
            return "Inactive"
        today = timezone.localdate()
        if today < self.start_date:
            return "Upcoming"
        elif self.start_date <= today <= self.end_date:
            return "Ongoing"
        else:
            return "Completed"

    @property
    def badge_color(self):
        """Returns the CSS badge class for current status."""
        status = self.timeline_status
        if status == "Ongoing":
            return "green"
        elif status == "Upcoming":
            return "amber"
        elif status == "Completed":
            return "violet"
        return "rose"


class ExamSchedule(models.Model):
    """
    Specific subject examination slot under an Exam.
    """
    STATUS_CHOICES = [
        ("Scheduled", "Scheduled"),
        ("Ongoing", "Ongoing"),
        ("Completed", "Completed"),
        ("Cancelled", "Cancelled"),
    ]

    exam = models.ForeignKey(Exam, on_delete=models.CASCADE, related_name="schedules", verbose_name="Exam")
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name="exam_sessions", verbose_name="Subject")
    exam_date = models.DateField(verbose_name="Exam Date")
    start_time = models.TimeField(verbose_name="Start Time")
    end_time = models.TimeField(verbose_name="End Time")
    room_number = models.CharField(max_length=60, blank=True, verbose_name="Room Number")
    room = models.CharField(max_length=60, blank=True, verbose_name="Hall / Room No.")
    invigilator = models.ForeignKey(
        Faculty,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="exam_duty_schedules",
        verbose_name="Invigilator"
    )
    max_marks = models.PositiveIntegerField(default=100, verbose_name="Maximum Marks")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="Scheduled", verbose_name="Exam Status")

    class Meta:
        ordering = ["exam_date", "start_time"]
        verbose_name = "Exam Schedule Slot"
        verbose_name_plural = "Exam Schedule Slots"
        constraints = [
            models.UniqueConstraint(
                fields=["exam", "subject"],
                name="unique_exam_subject"
            )
        ]

    def __str__(self):
        return f"{self.exam.name} - {self.subject.name} on {self.exam_date} ({self.status})"

    def save(self, *args, **kwargs):
        # Sync room_number and room so both fields remain populated
        if self.room_number and not self.room:
            self.room = self.room_number
        elif self.room and not self.room_number:
            self.room_number = self.room
        super().save(*args, **kwargs)


class StudentExamMark(models.Model):
    """
    Student Examination Marks and Automatic Result Computation.
    """
    RESULT_CHOICES = [
        ("Pass", "Pass"),
        ("Fail", "Fail"),
        ("Absent", "Absent"),
    ]

    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name="exam_marks", verbose_name="Student")
    exam = models.ForeignKey(Exam, on_delete=models.CASCADE, related_name="student_marks", verbose_name="Exam")
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name="exam_marks", verbose_name="Subject")
    exam_schedule = models.ForeignKey(ExamSchedule, on_delete=models.SET_NULL, null=True, blank=True, related_name="marks", verbose_name="Exam Schedule Slot")

    max_marks = models.PositiveIntegerField(default=100, verbose_name="Maximum Marks")
    marks_obtained = models.DecimalField(max_digits=5, decimal_places=2, default=0.00, verbose_name="Marks Obtained")
    percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0.00, verbose_name="Percentage")
    grade = models.CharField(max_length=5, blank=True, verbose_name="Grade")
    grade_point = models.DecimalField(max_digits=4, decimal_places=2, default=0.00, verbose_name="Grade Point")
    result_status = models.CharField(max_length=15, choices=RESULT_CHOICES, default="Pass", verbose_name="Result Status")
    remarks = models.CharField(max_length=255, blank=True, verbose_name="Remarks")

    entered_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="entered_exam_marks")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-exam__start_date", "subject__name", "student__roll_no"]
        verbose_name = "Student Exam Mark"
        verbose_name_plural = "Student Exam Marks"
        constraints = [
            models.UniqueConstraint(
                fields=["student", "exam", "subject"],
                name="unique_student_exam_subject_mark"
            )
        ]

    def __str__(self):
        return f"{self.student.name} ({self.student.roll_no}) - {self.exam.name} - {self.subject.name}: {self.marks_obtained}/{self.max_marks} ({self.grade})"

    def clean(self):
        super().clean()
        if self.marks_obtained is not None:
            if self.marks_obtained < 0:
                raise ValidationError({"marks_obtained": "Marks obtained cannot be negative."})
            if self.max_marks is not None and self.marks_obtained > self.max_marks:
                raise ValidationError({"marks_obtained": f"Marks obtained ({self.marks_obtained}) cannot be greater than maximum marks ({self.max_marks})."})

    def save(self, *args, **kwargs):
        # Enforce validation
        if self.marks_obtained is not None and self.max_marks is not None:
            if self.marks_obtained < 0:
                raise ValidationError("Marks obtained cannot be negative.")
            if self.marks_obtained > self.max_marks:
                raise ValidationError(f"Marks obtained ({self.marks_obtained}) cannot be greater than maximum marks ({self.max_marks}).")

        # Automatic calculation of Percentage, Grade, Grade Point and Pass/Fail status
        if self.result_status == "Absent":
            self.marks_obtained = 0
            self.percentage = 0.00
            self.grade = "AB"
            self.grade_point = 0.00
        elif self.max_marks > 0 and self.marks_obtained is not None:
            self.percentage = round((float(self.marks_obtained) / float(self.max_marks)) * 100, 2)
            grd, gpt, res = compute_grade_and_points(self.percentage)
            self.grade = grd
            self.grade_point = gpt
            self.result_status = res

        super().save(*args, **kwargs)

    @classmethod
    def get_student_exam_report(cls, student, exam):
        """
        Calculates student overall result and subject breakdown for a given exam.
        """
        marks = list(cls.objects.filter(student=student, exam=exam).select_related("subject", "exam_schedule"))
        if not marks:
            return None

        total_obtained = sum(m.marks_obtained for m in marks)
        total_max = sum(m.max_marks for m in marks)
        overall_pct = round((float(total_obtained) / float(total_max)) * 100, 2) if total_max > 0 else 0.0
        all_passed = all(m.result_status == "Pass" for m in marks)
        overall_result = "Pass" if all_passed else "Fail"
        overall_grade, overall_gp, _ = compute_grade_and_points(overall_pct)

        return {
            "exam": exam,
            "marks": marks,
            "total_obtained": total_obtained,
            "total_max": total_max,
            "overall_percentage": overall_pct,
            "overall_result": overall_result,
            "overall_grade": overall_grade,
            "overall_grade_point": overall_gp,
            "passed_count": sum(1 for m in marks if m.result_status == "Pass"),
            "failed_count": sum(1 for m in marks if m.result_status != "Pass"),
            "total_subjects": len(marks),
        }
