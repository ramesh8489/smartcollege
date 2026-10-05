from django.contrib import admin
from .models import (
    Company,
    PlacementDrive,
    PlacementApplication,
    PlacementRound,
    PlacementResult,
    StudentPlacementProfile,
)


@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = ["name", "industry", "hr_contact_person", "contact_email", "contact_phone", "status", "created_at"]
    list_filter = ["status", "industry", "created_at"]
    search_fields = ["name", "industry", "hr_contact_person", "contact_email", "description"]
    ordering = ["name"]
    date_hierarchy = "created_at"


class PlacementRoundInline(admin.TabularInline):
    model = PlacementRound
    extra = 0
    fields = ["round_number", "round_name", "round_type", "scheduled_date", "start_time", "location", "result", "score"]


@admin.register(PlacementDrive)
class PlacementDriveAdmin(admin.ModelAdmin):
    list_display = [
        "job_title",
        "company",
        "employment_type",
        "salary_package",
        "minimum_percentage",
        "maximum_backlogs",
        "eligible_year",
        "application_deadline",
        "drive_date",
        "status",
    ]
    list_filter = ["status", "employment_type", "eligible_year", "drive_date", "application_deadline", "company"]
    search_fields = ["job_title", "company__name", "job_location", "salary_package", "description"]
    ordering = ["-drive_date"]
    date_hierarchy = "drive_date"
    filter_horizontal = ["eligible_departments", "eligible_courses"]
    raw_id_fields = ["company"]


@admin.register(PlacementApplication)
class PlacementApplicationAdmin(admin.ModelAdmin):
    list_display = [
        "student",
        "placement_drive",
        "application_date",
        "status",
        "eligibility_status",
        "current_round",
    ]
    list_filter = [
        "status",
        "eligibility_status",
        "application_date",
        "placement_drive__company",
        "placement_drive__employment_type",
        "student__department",
        "student__course",
    ]
    search_fields = [
        "student__name",
        "student__roll_no",
        "placement_drive__job_title",
        "placement_drive__company__name",
        "current_round",
        "remarks",
    ]
    ordering = ["-application_date"]
    date_hierarchy = "application_date"
    raw_id_fields = ["student", "placement_drive"]
    inlines = [PlacementRoundInline]


@admin.register(PlacementRound)
class PlacementRoundAdmin(admin.ModelAdmin):
    list_display = [
        "round_number",
        "round_name",
        "application",
        "round_type",
        "scheduled_date",
        "start_time",
        "location",
        "result",
        "score",
    ]
    list_filter = ["result", "round_type", "scheduled_date"]
    search_fields = [
        "round_name",
        "application__student__name",
        "application__student__roll_no",
        "application__placement_drive__company__name",
        "location",
        "interviewer",
    ]
    ordering = ["-scheduled_date", "round_number"]
    date_hierarchy = "scheduled_date"
    raw_id_fields = ["application"]


@admin.register(PlacementResult)
class PlacementResultAdmin(admin.ModelAdmin):
    list_display = [
        "student",
        "company",
        "job_title",
        "ctc",
        "placement_type",
        "result",
        "result_date",
        "joining_date",
    ]
    list_filter = ["result", "placement_type", "result_date", "company"]
    search_fields = [
        "student__name",
        "student__roll_no",
        "company__name",
        "job_title",
        "ctc",
        "remarks",
    ]
    ordering = ["-result_date"]
    date_hierarchy = "result_date"
    raw_id_fields = ["student", "company", "placement_drive"]


@admin.register(StudentPlacementProfile)
class StudentPlacementProfileAdmin(admin.ModelAdmin):
    list_display = ["student", "cgpa_or_percentage", "active_backlogs", "skills", "updated_at"]
    search_fields = ["student__name", "student__roll_no", "skills", "bio"]
    raw_id_fields = ["student"]
