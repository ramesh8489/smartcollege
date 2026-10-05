from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True
    dependencies = [
        ("students", "0005_student_professional_profile"),
    ]
    operations = [
        migrations.CreateModel(
            name="Book",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("title", models.CharField(max_length=200)),
                ("author", models.CharField(max_length=150)),
                ("isbn", models.CharField(blank=True, max_length=30)),
                ("category", models.CharField(choices=[("TEXTBOOK", "Textbook"), ("REFERENCE", "Reference"), ("JOURNAL", "Journal"), ("GENERAL", "General")], default="TEXTBOOK", max_length=20)),
                ("publisher", models.CharField(blank=True, max_length=150)),
                ("total_copies", models.PositiveIntegerField(default=1)),
                ("available_copies", models.PositiveIntegerField(default=1)),
                ("shelf_location", models.CharField(blank=True, max_length=80)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={"ordering": ["title"]},
        ),
        migrations.CreateModel(
            name="BookLoan",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("issue_date", models.DateField()),
                ("due_date", models.DateField()),
                ("return_date", models.DateField(blank=True, null=True)),
                ("fine_amount", models.DecimalField(decimal_places=2, default=0, max_digits=8)),
                ("status", models.CharField(choices=[("ISSUED", "Issued"), ("RETURNED", "Returned"), ("OVERDUE", "Overdue")], default="ISSUED", max_length=10)),
                ("remarks", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("book", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="loans", to="library.book")),
                ("student", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="library_loans", to="students.student")),
            ],
            options={"ordering": ["-issue_date", "-created_at"]},
        ),
    ]
