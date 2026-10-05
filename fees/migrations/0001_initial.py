# Generated manually for the SmartCollege Fees module.
from django.db import migrations, models
import django.core.validators
import django.db.models.deletion
import django.utils.timezone
from decimal import Decimal


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("students", "0005_student_professional_profile"),
    ]

    operations = [
        migrations.CreateModel(
            name="FeeRecord",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("fee_type", models.CharField(choices=[("TUITION", "Tuition Fee"), ("EXAM", "Examination Fee"), ("HOSTEL", "Hostel Fee"), ("TRANSPORT", "Transport Fee"), ("LIBRARY", "Library Fee"), ("OTHER", "Other Fee")], max_length=20)),
                ("title", models.CharField(max_length=150)),
                ("academic_year", models.CharField(default="2026-27", max_length=20)),
                ("semester", models.PositiveIntegerField(blank=True, null=True)),
                ("due_date", models.DateField(blank=True, null=True)),
                ("amount", models.DecimalField(decimal_places=2, max_digits=10, validators=[django.core.validators.MinValueValidator(Decimal("0.00"))])),
                ("status", models.CharField(choices=[("PENDING", "Pending"), ("PARTIAL", "Partially Paid"), ("PAID", "Paid")], default="PENDING", max_length=10)),
                ("remarks", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("student", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="fee_records", to="students.student")),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.CreateModel(
            name="FeePayment",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("receipt_number", models.CharField(max_length=50, unique=True)),
                ("amount", models.DecimalField(decimal_places=2, max_digits=10, validators=[django.core.validators.MinValueValidator(Decimal("0.01"))])),
                ("payment_date", models.DateField(default=django.utils.timezone.now)),
                ("payment_mode", models.CharField(choices=[("CASH", "Cash"), ("UPI", "UPI"), ("CARD", "Card"), ("BANK", "Bank Transfer")], max_length=10)),
                ("reference_number", models.CharField(blank=True, max_length=100)),
                ("remarks", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("fee_record", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="payments", to="fees.feerecord")),
            ],
            options={"ordering": ["-payment_date", "-created_at"]},
        ),
    ]
