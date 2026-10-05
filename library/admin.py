from django.contrib import admin

from .models import Book, BookLoan


@admin.register(Book)
class BookAdmin(admin.ModelAdmin):

    list_display = (
        "title",
        "author",
        "category",
        "total_copies",
        "available_copies_display",
        "issued_copies_display",
        "is_active",
    )

    list_filter = (
        "category",
        "is_active",
    )

    search_fields = (
        "title",
        "author",
        "isbn",
        "publisher",
    )

    list_editable = (
        "is_active",
    )

    ordering = (
        "title",
    )

    readonly_fields = (
        "issued_copies_display",
        "created_at",
    )

    @admin.display(
        description="Available copies",
        ordering="available_copies"
    )
    def available_copies_display(self, obj):
        return obj.available_copies

    @admin.display(
        description="Issued copies"
    )
    def issued_copies_display(self, obj):
        return obj.issued_copies


@admin.register(BookLoan)
class BookLoanAdmin(admin.ModelAdmin):

    list_display = (
        "book",
        "student",
        "issue_date",
        "due_date",
        "return_date",
        "status",
        "fine_amount",
    )

    list_filter = (
        "status",
        "issue_date",
        "due_date",
    )

    search_fields = (
        "book__title",
        "student__name",
        "student__roll_no",
    )

    autocomplete_fields = (
        "book",
        "student",
    )

    readonly_fields = (
        "fine_amount",
        "created_at",
    )

    date_hierarchy = "issue_date"

    ordering = (
        "-issue_date",
        "-created_at",
    )