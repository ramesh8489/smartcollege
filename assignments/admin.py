from django.contrib import admin
from .models import Assignment, AssignmentSubmission


class AssignmentSubmissionInline(admin.TabularInline):
    model = AssignmentSubmission
    extra = 0
    fields = (
        "student",
        "submission_file",
        "status",
        "submitted_at",
        "marks_obtained",
        "percentage",
        "feedback",
    )
    readonly_fields = ("submitted_at", "percentage")
    autocomplete_fields = ("student",)


@admin.register(Assignment)
class AssignmentAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "subject",
        "faculty",
        "course",
        "year",
        "semester",
        "assignment_type",
        "assigned_date",
        "submission_deadline",
        "max_marks",
        "is_active",
        "display_submissions",
    )
    list_filter = (
        "assignment_type",
        "is_active",
        "academic_year",
        "course",
        "year",
        "semester",
        "assigned_date",
    )
    search_fields = (
        "title",
        "description",
        "instructions",
        "subject__name",
        "subject__code",
        "faculty__name",
    )
    ordering = ["-submission_deadline", "-created_at"]
    date_hierarchy = "submission_deadline"
    autocomplete_fields = ("faculty", "subject", "course")
    list_editable = ("is_active",)
    inlines = [AssignmentSubmissionInline]

    fieldsets = (
        ("Basic Information", {
            "fields": ("title", "assignment_type", "description", "instructions", "is_active")
        }),
        ("Academic Target", {
            "fields": ("faculty", "subject", "course", "year", "semester", "academic_year")
        }),
        ("Deadlines & Assessment", {
            "fields": ("assigned_date", "submission_deadline", "max_marks", "attachment")
        }),
    )

    @admin.display(description="Submissions")
    def display_submissions(self, obj):
        total = obj.submissions.count()
        evaluated = obj.submissions.filter(status="Evaluated").count()
        return f"{total} ({evaluated} evaluated)"


@admin.register(AssignmentSubmission)
class AssignmentSubmissionAdmin(admin.ModelAdmin):
    list_display = (
        "student",
        "assignment",
        "status",
        "submitted_at",
        "marks_obtained",
        "percentage",
        "evaluated_by",
        "evaluated_at",
    )
    list_filter = (
        "status",
        "assignment__assignment_type",
        "assignment__course",
        "submitted_at",
        "evaluated_at",
    )
    search_fields = (
        "student__name",
        "student__roll_no",
        "student__sif_number",
        "assignment__title",
        "feedback",
        "student_remarks",
    )
    ordering = ["-submitted_at"]
    autocomplete_fields = ("assignment", "student", "evaluated_by")
    readonly_fields = ("submitted_at", "updated_at", "percentage", "evaluated_at")

    fieldsets = (
        ("Assignment & Student", {
            "fields": ("assignment", "student")
        }),
        ("Submission Content", {
            "fields": ("submission_file", "student_remarks", "status", "submitted_at", "updated_at")
        }),
        ("Evaluation & Grading", {
            "fields": ("marks_obtained", "percentage", "feedback", "evaluated_by", "evaluated_at")
        }),
    )

    def save_model(self, request, obj, form, change):
        if obj.marks_obtained is not None and not obj.evaluated_by:
            obj.evaluated_by = request.user
        super().save_model(request, obj, form, change)
