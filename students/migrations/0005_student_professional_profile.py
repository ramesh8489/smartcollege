from django.db import migrations, models
from django.utils import timezone


class Migration(migrations.Migration):
    dependencies = [
        ("students", "0004_student_sif_number_course_student_course"),
    ]

    operations = [
        migrations.AddField(model_name="student", name="parent_name", field=models.CharField(blank=True, max_length=100)),
        migrations.AddField(model_name="student", name="parent_phone", field=models.CharField(blank=True, max_length=20)),
        migrations.AddField(model_name="student", name="phone", field=models.CharField(blank=True, max_length=20)),
        migrations.AddField(model_name="student", name="admission_date", field=models.DateField(default=timezone.now)),
        migrations.AddField(model_name="student", name="is_active", field=models.BooleanField(default=True)),
    ]
