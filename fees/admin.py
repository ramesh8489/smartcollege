from django.contrib import admin

from .models import FeePayment, FeeRecord


class FeePaymentInline(admin.TabularInline):
    model = FeePayment
    extra = 0
    fields = (
        "receipt_number",
        "amount",
        "payment_date",
        "payment_mode",
        "reference_number",
        "remarks",
    )


@admin.register(FeeRecord)
class FeeRecordAdmin(admin.ModelAdmin):
    list_display = (
        "student",
        "fee_type",
        "title",
        "academic_year",
        "amount",
        "display_paid",
        "display_balance",
        "display_status",
        "due_date",
    )
    list_filter = ("fee_type", "status", "academic_year", "due_date")
    search_fields = (
        "student__name",
        "student__roll_no",
        "student__sif_number",
        "title",
    )
    autocomplete_fields = ("student",)
    inlines = [FeePaymentInline]

    @admin.display(description="Paid")
    def display_paid(self, obj):
        return f"₹{obj.paid_amount:,.2f}"

    @admin.display(description="Balance")
    def display_balance(self, obj):
        return f"₹{obj.balance_amount:,.2f}"

    @admin.display(description="Status")
    def display_status(self, obj):
        return obj.computed_status


@admin.register(FeePayment)
class FeePaymentAdmin(admin.ModelAdmin):
    list_display = (
        "receipt_number",
        "fee_record",
        "amount",
        "payment_date",
        "payment_mode",
        "reference_number",
    )
    list_filter = ("payment_mode", "payment_date")
    search_fields = (
        "receipt_number",
        "reference_number",
        "fee_record__student__name",
        "fee_record__student__roll_no",
    )
    autocomplete_fields = ("fee_record",)
