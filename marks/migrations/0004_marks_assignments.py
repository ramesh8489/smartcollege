from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("marks", "0003_marks_unique_student_subject_marks"),
    ]

    operations = [
        migrations.AddField(
            model_name="marks",
            name="cat_1_assignment",
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name="marks",
            name="cat_2_assignment",
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name="marks",
            name="cat_3_assignment",
            field=models.IntegerField(default=0),
        ),
    ]
