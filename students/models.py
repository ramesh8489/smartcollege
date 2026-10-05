from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone


class Department(models.Model):
    """
    A School (e.g. "School of Computer Science"). The field/class
    is still named Department in the code to avoid touching every
    other app that links to it — treat "Department" and "School"
    as the same thing here.
    """

    name = models.CharField(max_length=100)

    def __str__(self):
        return self.name


class Course(models.Model):
    """
    A degree program offered by a School, e.g. "MSc AI & Data
    Science" under "School of Computer Science". A School
    (Department) can offer many Courses.
    """

    name = models.CharField(max_length=100)
    department = models.ForeignKey(
        Department,
        on_delete=models.CASCADE,
        related_name="courses"
    )

    def __str__(self):
        return f"{self.name} ({self.department.name})"


class Student(models.Model):
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        null=True,
        blank=True
    )

    name = models.CharField(max_length=100)
    roll_no = models.CharField(max_length=20, unique=True)

    # SIF number: the unique admission number the university
    # issues to every student when they join college, regardless
    # of school/course.
    sif_number = models.CharField(
        max_length=30,
        unique=True,
        null=True,
        blank=True
    )

    email = models.EmailField()
    department = models.ForeignKey(
        Department,
        on_delete=models.CASCADE
    )
    course = models.ForeignKey(
        Course,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    year = models.IntegerField()
    is_approved = models.BooleanField(default=True)

    # Professional student profile fields
    parent_name = models.CharField(max_length=100, blank=True)
    parent_phone = models.CharField(max_length=20, blank=True)
    phone = models.CharField(max_length=20, blank=True)
    admission_date = models.DateField(default=timezone.now)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name