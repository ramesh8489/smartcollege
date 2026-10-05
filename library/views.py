from datetime import timedelta
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from students.models import Student
from .models import Book, BookLoan


def _student(request):
    return Student.objects.filter(user=request.user, is_active=True).first()


@login_required(login_url="/accounts/login/")
def dashboard(request):
    is_admin = request.user.is_superuser
    student = _student(request)

    if not is_admin and not student:
        return redirect("/accounts/login/")

    books = Book.objects.filter(is_active=True).order_by("title")
    if request.GET.get("q"):
        q = request.GET["q"].strip()
        books = books.filter(title__icontains=q) | books.filter(author__icontains=q)
    books = books.distinct()

    if is_admin:
        loans = BookLoan.objects.select_related("book", "student").all()
    else:
        loans = BookLoan.objects.select_related("book", "student").filter(student=student)

    active_loans = loans.exclude(status="RETURNED")
    overdue_count = sum(1 for loan in active_loans if loan.current_status == "OVERDUE")
    available_count = sum(book.available_copies for book in books)

    student_list = Student.objects.filter(is_active=True).order_by("name") if is_admin else []

    context = {
        "student": student,
        "books": books,
        "loans": loans,
        "active_loans": active_loans,
        "overdue_count": overdue_count,
        "available_count": available_count,
        "is_admin": is_admin,
        "student_list": student_list,
    }
    return render(request, "library/dashboard.html", context)


@login_required(login_url="/accounts/login/")
def issue_book(request):
    if not request.user.is_superuser:
        return redirect("/library/")
    if request.method != "POST":
        return redirect("/library/")

    book = get_object_or_404(Book, pk=request.POST.get("book_id"), is_active=True)
    student = get_object_or_404(Student, pk=request.POST.get("student_id"), is_active=True)
    days = int(request.POST.get("days") or 14)
    days = min(max(days, 1), 60)

    if book.available_copies < 1:
        messages.error(request, "No available copy for this book.")
        return redirect("/library/")

    if BookLoan.objects.filter(book=book, student=student, return_date__isnull=True).exists():
        messages.error(request, "This student already has this book issued.")
        return redirect("/library/")

    with transaction.atomic():
        loan = BookLoan.objects.create(
            book=book,
            student=student,
            issue_date=timezone.localdate(),
            due_date=timezone.localdate() + timedelta(days=days),
        )
        Book.objects.filter(pk=book.pk).update(available_copies=book.available_copies - 1)

    messages.success(request, f"{book.title} issued to {student.name}.")
    return redirect("/library/")


@login_required(login_url="/accounts/login/")
def return_book(request, loan_id):
    if not request.user.is_superuser:
        return redirect("/library/")
    if request.method != "POST":
        return redirect("/library/")

    with transaction.atomic():
        loan = get_object_or_404(BookLoan.objects.select_related("book"), pk=loan_id)
        if loan.return_date:
            messages.info(request, "This book has already been returned.")
            return redirect("/library/")
        loan.return_date = timezone.localdate()
        loan.save()
        Book.objects.filter(pk=loan.book_id).update(
            available_copies=min(loan.book.total_copies, loan.book.available_copies + 1)
        )

    if loan.fine_amount:
        messages.success(request, f"Book returned. Fine calculated: ₹{loan.fine_amount:.2f}.")
    else:
        messages.success(request, "Book returned successfully.")
    return redirect("/library/")
