from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.utils import timezone

from students.models import Student


class Book(models.Model):
    CATEGORY_CHOICES = [
        ("TEXTBOOK", "Textbook"),
        ("REFERENCE", "Reference"),
        ("JOURNAL", "Journal"),
        ("GENERAL", "General"),
    ]

    title = models.CharField(max_length=200)
    author = models.CharField(max_length=150)
    isbn = models.CharField(max_length=30, blank=True)
    category = models.CharField(
        max_length=20,
        choices=CATEGORY_CHOICES,
        default="TEXTBOOK",
    )
    publisher = models.CharField(max_length=150, blank=True)
    total_copies = models.PositiveIntegerField(default=1)
    available_copies = models.PositiveIntegerField(default=1)
    shelf_location = models.CharField(max_length=80, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["title"]

    def __str__(self):
        return f"{self.title} — {self.author}"

    @property
    def issued_copies(self):
        return max(self.total_copies - self.available_copies, 0)


class BookLoan(models.Model):
    STATUS_CHOICES = [
        ("ISSUED", "Issued"),
        ("RETURNED", "Returned"),
        ("OVERDUE", "Overdue"),
    ]

    book = models.ForeignKey(
        Book,
        on_delete=models.PROTECT,
        related_name="loans",
    )
    student = models.ForeignKey(
        Student,
        on_delete=models.CASCADE,
        related_name="library_loans",
    )
    issue_date = models.DateField(default=timezone.now)
    due_date = models.DateField()
    return_date = models.DateField(null=True, blank=True)
    fine_amount = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        default=0,
    )
    status = models.CharField(
        max_length=10,
        choices=STATUS_CHOICES,
        default="ISSUED",
    )
    remarks = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-issue_date", "-created_at"]

    def __str__(self):
        return f"{self.book.title} — {self.student.name}"

    @property
    def current_status(self):
        if self.return_date:
            return "RETURNED"

        if self.due_date and self.due_date < timezone.localdate():
            return "OVERDUE"

        return "ISSUED"

    @property
    def calculated_fine(self):
        if self.return_date:
            end_date = self.return_date
        else:
            end_date = timezone.localdate()

        if not self.due_date or end_date <= self.due_date:
            return 0

        return (end_date - self.due_date).days * 5

    def clean(self):
        if (
            self.issue_date
            and self.due_date
            and self.due_date < self.issue_date
        ):
            raise ValidationError({
                "due_date": "Due date cannot be before issue date."
            })

    @transaction.atomic
    def save(self, *args, **kwargs):
        self.full_clean()

        # Check whether this is an existing loan
        old_loan = None

        if self.pk:
            try:
                old_loan = BookLoan.objects.select_related(
                    "book"
                ).get(pk=self.pk)
            except BookLoan.DoesNotExist:
                old_loan = None

        # Update status and fine
        if self.return_date:
            self.status = "RETURNED"
            self.fine_amount = self.calculated_fine
        else:
            self.status = self.current_status
            self.fine_amount = self.calculated_fine

        # Save loan
        super().save(*args, **kwargs)

        # Get fresh book object
        book = Book.objects.select_for_update().get(pk=self.book_id)

        # New loan
        if old_loan is None:
            if self.status in ("ISSUED", "OVERDUE"):
                if book.available_copies > 0:
                    book.available_copies -= 1
                    book.save(update_fields=["available_copies"])

        # Existing loan changed
        else:
            old_active = old_loan.status in ("ISSUED", "OVERDUE")
            new_active = self.status in ("ISSUED", "OVERDUE")

            # Issued -> Returned
            if old_active and not new_active:
                if book.available_copies < book.total_copies:
                    book.available_copies += 1
                    book.save(update_fields=["available_copies"])

            # Returned -> Issued
            elif not old_active and new_active:
                if book.available_copies > 0:
                    book.available_copies -= 1
                    book.save(update_fields=["available_copies"])

            # Book changed while loan is active
            elif old_active and new_active and old_loan.book_id != self.book_id:
                old_book = Book.objects.select_for_update().get(
                    pk=old_loan.book_id
                )

                if old_book.available_copies < old_book.total_copies:
                    old_book.available_copies += 1
                    old_book.save(update_fields=["available_copies"])

                if book.available_copies > 0:
                    book.available_copies -= 1
                    book.save(update_fields=["available_copies"])