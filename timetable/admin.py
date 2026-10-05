from django.contrib import admin

from .models import (
    Period,
    SchoolClass,
    Timetable,
    SchoolIncharge,
    Circular,
    FacultyLeaveRequest,
    Notification,
    Exam,
)


@admin.register(Period)
class PeriodAdmin(admin.ModelAdmin):
    list_display = ("period_number", "start_time", "end_time")


@admin.register(SchoolClass)
class SchoolClassAdmin(admin.ModelAdmin):
    list_display = ("__str__", "department", "course", "year")
    list_filter = ("department",)


@admin.register(Timetable)
class TimetableAdmin(admin.ModelAdmin):
    list_display = (
        "day_of_week",
        "period",
        "school_class",
        "subject",
        "faculty",
    )
    list_filter = ("day_of_week", "school_class__department")


@admin.register(SchoolIncharge)
class SchoolInchargeAdmin(admin.ModelAdmin):
    list_display = ("department", "faculty")


@admin.register(Circular)
class CircularAdmin(admin.ModelAdmin):
    list_display = ("title", "audience", "posted_by", "posted_at")
    list_filter = ("audience",)


@admin.register(FacultyLeaveRequest)
class FacultyLeaveRequestAdmin(admin.ModelAdmin):
    list_display = (
        "faculty",
        "department",
        "from_date",
        "to_date",
        "status",
        "forwarded_to_admin",
        "admin_seen",
        "created_at",
    )
    list_filter = ("status", "forwarded_to_admin", "admin_seen", "department")
    search_fields = ("faculty__name", "faculty__faculty_id", "reason")


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("recipient", "title", "is_read", "created_at")
    list_filter = ("is_read",)
    search_fields = ("recipient__username", "title", "message")


@admin.register(Exam)
class ExamAdmin(admin.ModelAdmin):
    list_display = ("name", "exam_type", "school_class", "subject", "exam_date", "start_time", "room", "invigilator", "published")
    list_filter = ("exam_type", "published", "exam_date", "school_class__department")
    search_fields = ("name", "subject__name", "school_class__course__name")
