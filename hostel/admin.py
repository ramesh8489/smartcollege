from django.contrib import admin
from .models import (
    Hostel,
    HostelBlock,
    HostelFloor,
    HostelRoom,
    HostelBed,
    HostelApplication,
    HostelAllocation,
    HostelCheckInOut,
    HostelRoomTransfer,
    HostelAttendance,
    HostelComplaint,
    HostelWarden,
    HostelNotice,
    HostelVisitor,
)


class HostelBlockInline(admin.TabularInline):
    model = HostelBlock
    extra = 1
    fields = ("name", "code", "is_active")


class HostelWardenInline(admin.TabularInline):
    model = HostelWarden
    extra = 1
    fields = ("user", "role", "designation", "contact_number", "is_active")
    autocomplete_fields = ("user",)


@admin.register(Hostel)
class HostelAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "code",
        "hostel_type",
        "warden_incharge",
        "total_rooms",
        "total_beds",
        "occupied_beds",
        "available_beds",
        "occupancy_percentage",
        "is_active",
    )
    list_filter = ("hostel_type", "is_active", "created_at")
    search_fields = ("name", "code", "address", "contact_phone", "contact_email")
    readonly_fields = ("created_at", "updated_at")
    inlines = [HostelBlockInline, HostelWardenInline]
    ordering = ("name",)


class HostelFloorInline(admin.TabularInline):
    model = HostelFloor
    extra = 1
    fields = ("floor_number", "name", "is_active")


@admin.register(HostelBlock)
class HostelBlockAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "hostel", "is_active", "created_at")
    list_filter = ("hostel", "is_active")
    search_fields = ("name", "code", "hostel__name", "hostel__code")
    autocomplete_fields = ("hostel",)
    readonly_fields = ("created_at", "updated_at")
    inlines = [HostelFloorInline]
    ordering = ("hostel", "name")


@admin.register(HostelFloor)
class HostelFloorAdmin(admin.ModelAdmin):
    list_display = ("name", "floor_number", "block", "is_active", "created_at")
    list_filter = ("block__hostel", "is_active")
    search_fields = ("name", "block__name", "block__hostel__name")
    autocomplete_fields = ("block",)
    readonly_fields = ("created_at", "updated_at")
    ordering = ("block", "floor_number")


class HostelBedInline(admin.TabularInline):
    model = HostelBed
    extra = 1
    fields = ("bed_number", "status", "is_active", "remarks")


@admin.register(HostelRoom)
class HostelRoomAdmin(admin.ModelAdmin):
    list_display = (
        "room_number",
        "hostel",
        "block",
        "floor",
        "room_type",
        "capacity",
        "occupied_beds_count",
        "available_beds_count",
        "status",
        "monthly_rent",
        "is_active",
    )
    list_filter = ("hostel", "room_type", "status", "is_active")
    search_fields = ("room_number", "hostel__name", "block__name")
    autocomplete_fields = ("hostel", "block", "floor")
    readonly_fields = ("created_at", "updated_at")
    inlines = [HostelBedInline]
    ordering = ("hostel", "block", "floor", "room_number")


@admin.register(HostelBed)
class HostelBedAdmin(admin.ModelAdmin):
    list_display = ("bed_number", "room", "get_hostel", "status", "is_active", "updated_at")
    list_filter = ("status", "is_active", "room__hostel", "room__room_type")
    search_fields = ("bed_number", "room__room_number", "room__hostel__name")
    autocomplete_fields = ("room",)
    readonly_fields = ("created_at", "updated_at")
    ordering = ("room", "bed_number")

    @admin.display(description="Hostel")
    def get_hostel(self, obj):
        return obj.room.hostel.name


@admin.register(HostelApplication)
class HostelApplicationAdmin(admin.ModelAdmin):
    list_display = (
        "application_id",
        "student",
        "hostel_preference",
        "room_type_preference",
        "academic_year",
        "application_date",
        "status",
        "reviewed_by",
        "reviewed_date",
    )
    list_filter = ("status", "hostel_preference", "room_type_preference", "academic_year")
    search_fields = ("application_id", "student__name", "student__roll_no", "student__email")
    autocomplete_fields = ("student", "hostel_preference", "reviewed_by")
    readonly_fields = ("application_id", "created_at", "updated_at")
    ordering = ("-created_at",)


@admin.register(HostelAllocation)
class HostelAllocationAdmin(admin.ModelAdmin):
    list_display = (
        "allocation_id",
        "student",
        "hostel",
        "block",
        "room",
        "bed",
        "allocation_date",
        "status",
        "allocated_by",
    )
    list_filter = ("status", "hostel", "academic_year", "allocation_date")
    search_fields = (
        "allocation_id",
        "student__name",
        "student__roll_no",
        "room__room_number",
        "bed__bed_number",
    )
    autocomplete_fields = ("student", "hostel", "block", "floor", "room", "bed", "allocated_by")
    readonly_fields = ("allocation_id", "created_at", "updated_at")
    ordering = ("-allocation_date", "-created_at")


@admin.register(HostelCheckInOut)
class HostelCheckInOutAdmin(admin.ModelAdmin):
    list_display = (
        "student",
        "event_type",
        "event_date",
        "event_time",
        "allocation",
        "processed_by",
    )
    list_filter = ("event_type", "event_date")
    search_fields = (
        "student__name",
        "student__roll_no",
        "allocation__allocation_id",
        "reason",
    )
    autocomplete_fields = ("student", "allocation", "processed_by")
    readonly_fields = ("created_at",)
    ordering = ("-event_date", "-created_at")


@admin.register(HostelRoomTransfer)
class HostelRoomTransferAdmin(admin.ModelAdmin):
    list_display = (
        "student",
        "old_hostel",
        "old_room",
        "old_bed",
        "new_hostel",
        "new_room",
        "new_bed",
        "transfer_date",
        "approved_by",
    )
    list_filter = ("transfer_date", "new_hostel")
    search_fields = (
        "student__name",
        "student__roll_no",
        "reason",
        "old_room__room_number",
        "new_room__room_number",
    )
    autocomplete_fields = (
        "student",
        "allocation",
        "old_hostel",
        "new_hostel",
        "old_room",
        "new_room",
        "old_bed",
        "new_bed",
        "approved_by",
    )
    readonly_fields = ("created_at",)
    ordering = ("-transfer_date", "-created_at")


@admin.register(HostelAttendance)
class HostelAttendanceAdmin(admin.ModelAdmin):
    list_display = (
        "student",
        "hostel",
        "room",
        "date",
        "status",
        "marked_by",
        "updated_at",
    )
    list_filter = ("status", "date", "hostel")
    search_fields = (
        "student__name",
        "student__roll_no",
        "hostel__name",
        "room__room_number",
        "remarks",
    )
    autocomplete_fields = ("student", "hostel", "room", "marked_by")
    date_hierarchy = "date"
    readonly_fields = ("created_at", "updated_at")
    ordering = ("-date", "student__name")


@admin.register(HostelComplaint)
class HostelComplaintAdmin(admin.ModelAdmin):
    list_display = (
        "complaint_id",
        "title",
        "student",
        "hostel",
        "room",
        "category",
        "priority",
        "status",
        "assigned_staff",
        "created_at",
        "resolved_date",
    )
    list_filter = ("status", "category", "priority", "hostel")
    search_fields = (
        "complaint_id",
        "title",
        "description",
        "student__name",
        "student__roll_no",
        "resolution",
    )
    autocomplete_fields = ("student", "hostel", "room", "assigned_staff", "resolved_by")
    readonly_fields = ("complaint_id", "created_at", "updated_at", "resolved_date")
    ordering = ("-created_at",)


@admin.register(HostelWarden)
class HostelWardenAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "hostel",
        "role",
        "designation",
        "contact_number",
        "is_active",
        "assigned_date",
    )
    list_filter = ("role", "is_active", "hostel")
    search_fields = (
        "user__username",
        "user__first_name",
        "user__last_name",
        "user__email",
        "hostel__name",
        "designation",
    )
    autocomplete_fields = ("user", "hostel")
    readonly_fields = ("created_at", "updated_at")
    ordering = ("hostel__name", "role")


@admin.register(HostelNotice)
class HostelNoticeAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "hostel",
        "priority",
        "publish_date",
        "expiry_date",
        "is_active",
        "created_by",
    )
    list_filter = ("priority", "is_active", "hostel", "publish_date")
    search_fields = ("title", "message", "hostel__name")
    autocomplete_fields = ("hostel", "created_by")
    readonly_fields = ("created_at", "updated_at")
    ordering = ("-publish_date", "-created_at")


@admin.register(HostelVisitor)
class HostelVisitorAdmin(admin.ModelAdmin):
    list_display = (
        "visitor_name",
        "relationship",
        "student",
        "hostel",
        "phone",
        "visit_date",
        "entry_time",
        "exit_time",
        "status",
        "approved_by",
    )
    list_filter = ("status", "visit_date", "hostel")
    search_fields = ("visitor_name", "student__name", "student__roll_no", "phone", "purpose")
    autocomplete_fields = ("student", "hostel", "approved_by")
    readonly_fields = ("created_at", "updated_at")
    ordering = ("-visit_date", "-created_at")



