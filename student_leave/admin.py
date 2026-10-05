from django.contrib import admin
from .models import StudentLeaveRequest, StudentLeaveHistory


class StudentLeaveHistoryInline(admin.TabularInline):
    model = StudentLeaveHistory
    extra = 0
    can_delete = False
    readonly_fields = [
        "action",
        "previous_status",
        "new_status",
        "action_taken_by",
        "remarks",
        "timestamp",
    ]


@admin.register(StudentLeaveRequest)
class StudentLeaveRequestAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "student",
        "leave_type",
        "from_date",
        "to_date",
        "number_of_days",
        "status",
        "applied_date",
        "approved_rejected_by",
    ]
    list_filter = [
        "status",
        "leave_type",
        "from_date",
        "applied_date",
        "student__department",
        "student__course",
    ]
    search_fields = [
        "student__name",
        "student__roll_no",
        "reason",
        "student_remarks",
        "faculty_remarks",
        "incharge_remarks",
        "admin_remarks",
    ]
    ordering = ["-applied_date"]
    date_hierarchy = "applied_date"
    raw_id_fields = ["student", "approved_rejected_by"]
    readonly_fields = [
        "applied_date",
        "created_date",
        "updated_date",
        "approved_rejected_date",
    ]
    inlines = [StudentLeaveHistoryInline]

    fieldsets = (
        ("Student & Dates", {
            "fields": (
                "student",
                "leave_type",
                ("from_date", "to_date", "number_of_days"),
                "reason",
                "supporting_document",
            )
        }),
        ("Status & Workflow", {
            "fields": (
                "status",
                ("approved_rejected_by", "approved_rejected_date"),
            )
        }),
        ("Multi-Tier Remarks", {
            "fields": (
                "student_remarks",
                "faculty_remarks",
                "incharge_remarks",
                "admin_remarks",
            )
        }),
        ("Timestamps", {
            "fields": (
                "applied_date",
                "created_date",
                "updated_date",
            ),
            "classes": ("collapse",),
        }),
    )


@admin.register(StudentLeaveHistory)
class StudentLeaveHistoryAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "leave_request",
        "action",
        "previous_status",
        "new_status",
        "action_taken_by",
        "timestamp",
    ]
    list_filter = ["action", "new_status", "timestamp"]
    search_fields = [
        "leave_request__student__name",
        "leave_request__student__roll_no",
        "action",
        "remarks",
    ]
    ordering = ["-timestamp"]
    date_hierarchy = "timestamp"
    raw_id_fields = ["leave_request", "action_taken_by"]
    readonly_fields = [
        "leave_request",
        "action",
        "previous_status",
        "new_status",
        "action_taken_by",
        "remarks",
        "timestamp",
    ]
