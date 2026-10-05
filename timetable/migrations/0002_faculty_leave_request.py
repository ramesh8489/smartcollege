import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("faculty", "0004_faculty_is_approved"),
        ("students", "0004_student_sif_number_course_student_course"),
        ("timetable", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="FacultyLeaveRequest",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("from_date", models.DateField()),
                ("to_date", models.DateField()),
                ("reason", models.TextField()),
                ("status", models.CharField(
                    choices=[
                        ("PENDING", "Pending"),
                        ("APPROVED", "Approved by School Incharge"),
                        ("REJECTED", "Rejected by School Incharge"),
                    ],
                    default="PENDING",
                    max_length=20,
                )),
                ("incharge_comment", models.TextField(blank=True)),
                ("reviewed_at", models.DateTimeField(blank=True, null=True)),
                ("forwarded_to_admin", models.BooleanField(default=False)),
                ("admin_seen", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("department", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="faculty_leave_requests",
                    to="students.department",
                )),
                ("faculty", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="leave_requests",
                    to="faculty.faculty",
                )),
                ("reviewed_by", models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="reviewed_leave_requests",
                    to="faculty.faculty",
                )),
            ],
            options={
                "ordering": ["-created_at"],
            },
        ),
    ]
