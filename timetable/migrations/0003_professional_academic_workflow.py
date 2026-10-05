from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("timetable", "0002_faculty_leave_request"),
        ("faculty", "0005_faculty_profile_subject_academic"),
        ("students", "0005_student_professional_profile"),
    ]

    operations = [
        migrations.CreateModel(
            name="Notification",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("title", models.CharField(max_length=200)),
                ("message", models.TextField()),
                ("link", models.CharField(blank=True, max_length=300)),
                ("is_read", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("recipient", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="smartcollege_notifications", to="auth.user")),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.CreateModel(
            name="Exam",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=100)),
                ("exam_type", models.CharField(choices=[("CAT1", "CAT 1"), ("CAT2", "CAT 2"), ("CAT3", "CAT 3"), ("SEM", "Semester Exam"), ("PRACTICAL", "Practical Exam")], max_length=20)),
                ("exam_date", models.DateField()),
                ("start_time", models.TimeField()),
                ("end_time", models.TimeField()),
                ("room", models.CharField(blank=True, max_length=50)),
                ("max_marks", models.PositiveIntegerField(default=100)),
                ("published", models.BooleanField(default=False)),
                ("invigilator", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="invigilated_exams", to="faculty.faculty")),
                ("school_class", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="exams", to="timetable.schoolclass")),
                ("subject", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="exams", to="faculty.subject")),
            ],
            options={"ordering": ["exam_date", "start_time"]},
        ),
        migrations.AddField(model_name="circular", name="target_department", field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="target_circulars", to="students.department")),
        migrations.AddField(model_name="circular", name="target_course", field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="target_circulars", to="students.course")),
        migrations.AddField(model_name="circular", name="target_year", field=models.PositiveIntegerField(blank=True, null=True)),
        migrations.AddField(model_name="facultyleaverequest", name="leave_type", field=models.CharField(choices=[("CASUAL", "Casual Leave"), ("MEDICAL", "Medical Leave"), ("OD", "On Duty"), ("EMERGENCY", "Emergency Leave")], default="CASUAL", max_length=20)),
        migrations.AddField(model_name="facultyleaverequest", name="supporting_document", field=models.FileField(blank=True, null=True, upload_to="leave_documents/")),
    ]
