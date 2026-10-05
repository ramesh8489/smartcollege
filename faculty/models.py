from django.db import models
from django.contrib.auth.models import User
from students.models import Department


class Faculty(models.Model):
    user = models.OneToOneField(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )

    name = models.CharField(max_length=100)
    faculty_id = models.CharField(max_length=20, unique=True)
    email = models.EmailField()
    department = models.ForeignKey(Department, on_delete=models.CASCADE)
    is_approved = models.BooleanField(default=True)

    # Professional faculty profile fields
    phone = models.CharField(max_length=20, blank=True)
    designation = models.CharField(max_length=100, default="Faculty")
    joining_date = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name


class Subject(models.Model):
    SUBJECT_TYPE_CHOICES = [
        ("THEORY", "Theory"),
        ("PRACTICAL", "Practical"),
    ]

    name = models.CharField(max_length=100)
    code = models.CharField(max_length=20, unique=True)
    department = models.ForeignKey(Department, on_delete=models.CASCADE)
    faculty = models.ForeignKey(Faculty, on_delete=models.CASCADE)
    course = models.ForeignKey(
        "students.Course", on_delete=models.SET_NULL,
        null=True, blank=True, related_name="subjects"
    )
    year = models.PositiveIntegerField(null=True, blank=True)
    semester = models.PositiveIntegerField(null=True, blank=True)
    credits = models.DecimalField(max_digits=4, decimal_places=1, default=0)
    subject_type = models.CharField(max_length=20, choices=SUBJECT_TYPE_CHOICES, default="THEORY")

    def __str__(self):
        return self.name