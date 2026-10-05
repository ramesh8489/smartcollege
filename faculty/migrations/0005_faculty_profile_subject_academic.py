from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("faculty", "0004_faculty_is_approved"),
        ("students", "0004_student_sif_number_course_student_course"),
    ]

    operations = [
        migrations.AddField(model_name="faculty", name="phone", field=models.CharField(blank=True, max_length=20)),
        migrations.AddField(model_name="faculty", name="designation", field=models.CharField(default="Faculty", max_length=100)),
        migrations.AddField(model_name="faculty", name="joining_date", field=models.DateField(blank=True, null=True)),
        migrations.AddField(model_name="faculty", name="is_active", field=models.BooleanField(default=True)),
        migrations.AddField(model_name="subject", name="course", field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="subjects", to="students.course")),
        migrations.AddField(model_name="subject", name="year", field=models.PositiveIntegerField(blank=True, null=True)),
        migrations.AddField(model_name="subject", name="semester", field=models.PositiveIntegerField(blank=True, null=True)),
        migrations.AddField(model_name="subject", name="credits", field=models.DecimalField(decimal_places=1, default=0, max_digits=4)),
        migrations.AddField(model_name="subject", name="subject_type", field=models.CharField(choices=[("THEORY", "Theory"), ("PRACTICAL", "Practical")], default="THEORY", max_length=20)),
    ]
