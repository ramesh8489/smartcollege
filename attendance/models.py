from django.db import models
from students.models import Student
from faculty.models import Subject


class Attendance(models.Model):

    student = models.ForeignKey(
        Student,
        on_delete=models.CASCADE
    )

    subject = models.ForeignKey(
        Subject,
        on_delete=models.CASCADE
    )

    date = models.DateField()

    # Which hour/period this attendance was taken in. Nullable so
    # older records (taken before periods existed) still work.
    period = models.ForeignKey(
        "timetable.Period",
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )

    present = models.BooleanField(
        default=False
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["student", "subject", "date", "period"],
                name="unique_student_subject_date_period",
            )
        ]

    def __str__(self):
        status = "Present" if self.present else "Absent"

        return (
            f"{self.student.name} - "
            f"{self.subject.name} - "
            f"{status}"
        )