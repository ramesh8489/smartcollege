from decimal import Decimal

from django.core.validators import MinValueValidator
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from students.models import Student


class FeeRecord(models.Model):
    FEE_TYPE_CHOICES = [
        ("TUITION", "Tuition Fee"),
        ("EXAM", "Examination Fee"),
        ("HOSTEL", "Hostel Fee"),
        ("TRANSPORT", "Transport Fee"),
        ("LIBRARY", "Library Fee"),
        ("OTHER", "Other Fee"),
    ]

    STATUS_CHOICES = [
        ("PENDING", "Pending"),
        ("PARTIAL", "Partially Paid"),
        ("PAID", "Paid"),
    ]

    student = models.ForeignKey(
        Student,
        on_delete=models.CASCADE,
        related_name="fee_records",
    )
    fee_type = models.CharField(max_length=20, choices=FEE_TYPE_CHOICES)
    title = models.CharField(max_length=150)
    academic_year = models.CharField(max_length=20, default="2026-27")
    semester = models.PositiveIntegerField(null=True, blank=True)
    due_date = models.DateField(null=True, blank=True)
    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.00"))],
    )
    status = models.CharField(
        max_length=10,
        choices=STATUS_CHOICES,
        default="PENDING",
    )
    remarks = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.student.name} - {self.title} - ₹{self.amount}"

    @property
    def paid_amount(self):
        return sum(
            (payment.amount for payment in self.payments.all()),
            Decimal("0.00"),
        )

    @property
    def balance_amount(self):
        balance = self.amount - self.paid_amount
        return max(balance, Decimal("0.00"))

    @property
    def computed_status(self):
        paid = self.paid_amount
        if paid <= Decimal("0.00"):
            return "PENDING"
        if paid >= self.amount:
            return "PAID"
        return "PARTIAL"

    def save(self, *args, **kwargs):
        # Keep the stored status aligned when a fee record is saved.
        if self.pk:
            paid = self.paid_amount
            if paid <= Decimal("0.00"):
                self.status = "PENDING"
            elif paid >= self.amount:
                self.status = "PAID"
            else:
                self.status = "PARTIAL"
        super().save(*args, **kwargs)


class FeePayment(models.Model):
    PAYMENT_MODE_CHOICES = [
        ("CASH", "Cash"),
        ("UPI", "UPI"),
        ("CARD", "Card"),
        ("BANK", "Bank Transfer"),
    ]

    fee_record = models.ForeignKey(
        FeeRecord,
        on_delete=models.CASCADE,
        related_name="payments",
    )
    receipt_number = models.CharField(max_length=50, unique=True)
    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    payment_date = models.DateField(default=timezone.now)
    payment_mode = models.CharField(max_length=10, choices=PAYMENT_MODE_CHOICES)
    reference_number = models.CharField(max_length=100, blank=True)
    remarks = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-payment_date", "-created_at"]

    def clean(self):
        if self.fee_record_id and self.amount is not None:
            existing_paid = sum(
                (
                    payment.amount
                    for payment in self.fee_record.payments.exclude(pk=self.pk)
                ),
                Decimal("0.00"),
            )
            if existing_paid + self.amount > self.fee_record.amount:
                raise ValidationError({
                    "amount": "Payment cannot exceed the remaining fee balance."
                })

    def save(self, *args, **kwargs):
        self.full_clean()
        result = super().save(*args, **kwargs)
        fee = self.fee_record
        paid = fee.paid_amount
        if paid <= Decimal("0.00"):
            new_status = "PENDING"
        elif paid >= fee.amount:
            new_status = "PAID"
        else:
            new_status = "PARTIAL"
        if fee.status != new_status:
            FeeRecord.objects.filter(pk=fee.pk).update(status=new_status)
        return result

    def __str__(self):
        return f"{self.receipt_number} - {self.fee_record.student.name} - ₹{self.amount}"
