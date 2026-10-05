from django.contrib import admin
from .models import Exam, ExamSchedule, StudentExamMark


class ExamScheduleInline(admin.TabularInline):
    model = ExamSchedule
    extra = 1
    fields = ("subject", "exam_date", "start_time", "end_time", "room_number", "invigilator", "max_marks", "status")
    autocomplete_fields = ("subject", "invigilator")


@admin.register(Exam)
class ExamAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "exam_type",
        "academic_year",
        "semester",
        "course",
        "year",
        "start_date",
        "end_date",
        "is_active",
        "timeline_status",
    )
    list_filter = (
        "is_active",
        "exam_type",
        "academic_year",
        "course",
        "year",
        "semester",
    )
    search_fields = ("name", "course__name", "description", "academic_year")
    ordering = ["-start_date", "-created_at"]
    autocomplete_fields = ("course",)
    date_hierarchy = "start_date"
    list_editable = ("is_active",)
    inlines = [ExamScheduleInline]
    fieldsets = (
        ("Exam Details", {
            "fields": ("name", "exam_type", "description", "is_active")
        }),
        ("Academic Cohort & Degree", {
            "fields": ("academic_year", "course", "year", "semester")
        }),
        ("Schedule Timeline", {
            "fields": ("start_date", "end_date")
        }),
    )


@admin.register(ExamSchedule)
class ExamScheduleAdmin(admin.ModelAdmin):
    list_display = (
        "exam",
        "subject",
        "exam_date",
        "start_time",
        "end_time",
        "room_number",
        "invigilator",
        "max_marks",
        "status",
    )
    list_filter = (
        "status",
        "exam__exam_type",
        "exam_date",
        "exam__course",
        "exam__academic_year",
    )
    search_fields = (
        "exam__name",
        "subject__name",
        "subject__code",
        "room_number",
        "room",
        "invigilator__name",
    )
    ordering = ["exam_date", "start_time"]
    autocomplete_fields = ("exam", "subject", "invigilator")
    list_editable = ("status", "max_marks")


@admin.register(StudentExamMark)
class StudentExamMarkAdmin(admin.ModelAdmin):
    list_display = (
        "student",
        "exam",
        "subject",
        "marks_obtained",
        "max_marks",
        "percentage",
        "grade",
        "grade_point",
        "result_status",
        "updated_at",
    )
    list_filter = (
        "result_status",
        "grade",
        "exam__exam_type",
        "exam",
        "subject__course",
        "subject",
    )
    search_fields = (
        "student__name",
        "student__roll_no",
        "student__sif_number",
        "exam__name",
        "subject__name",
        "subject__code",
    )
    ordering = ["-exam__start_date", "subject__name", "student__roll_no"]
    autocomplete_fields = ("student", "exam", "subject")
    readonly_fields = ("percentage", "grade", "grade_point", "created_at", "updated_at")
    fieldsets = (
        ("Student & Examination", {
            "fields": ("student", "exam", "subject", "exam_schedule")
        }),
        ("Marks & Assessment", {
            "fields": ("max_marks", "marks_obtained", "result_status", "remarks")
        }),
        ("Computed Performance", {
            "fields": ("percentage", "grade", "grade_point"),
            "classes": ("collapse",)
        }),
        ("Audit Metadata", {
            "fields": ("entered_by", "created_at", "updated_at"),
            "classes": ("collapse",)
        }),
    )

    def save_model(self, request, obj, form, change):
        if not change and not obj.entered_by:
            obj.entered_by = request.user
        super().save_model(request, obj, form, change)
