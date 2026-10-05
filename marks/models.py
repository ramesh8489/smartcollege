from django.db import models
from students.models import Student
from faculty.models import Subject


class Marks(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE)
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE)

    # CAT exam marks: maximum 40 each.
    cat_1 = models.IntegerField(default=0)
    cat_2 = models.IntegerField(default=0)
    cat_3 = models.IntegerField(default=0)

    # Assignment marks attached to each CAT: maximum 10 each.
    cat_1_assignment = models.IntegerField(default=0)
    cat_2_assignment = models.IntegerField(default=0)
    cat_3_assignment = models.IntegerField(default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["student", "subject"],
                name="unique_student_subject_marks",
            )
        ]

    @property
    def cat_1_total(self):
        return self.cat_1 + self.cat_1_assignment

    @property
    def cat_2_total(self):
        return self.cat_2 + self.cat_2_assignment

    @property
    def cat_3_total(self):
        return self.cat_3 + self.cat_3_assignment

    @property
    def grand_total(self):
        return self.cat_1_total + self.cat_2_total + self.cat_3_total

    def __str__(self):
        return f"{self.student.name} - {self.subject.name}"
