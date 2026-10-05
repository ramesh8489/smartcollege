from django.contrib import admin
from .models import (
    Vehicle,
    Route,
    Stop,
    Driver,
    Conductor,
    TransportStaff,
    TransportApplication,
    TransportAllocation,
    TransportPass,
    TransportAttendance,
    VehicleMaintenance,
    TransportComplaint,
    TransportIncident,
)


class StopInline(admin.TabularInline):
    model = Stop
    extra = 1
    fields = ["stop_order", "stop_name", "stop_code", "pickup_time", "drop_time", "distance_km", "fare_amount", "is_active"]
    ordering = ["stop_order"]


@admin.register(Vehicle)
class VehicleAdmin(admin.ModelAdmin):
    list_display = [
        "vehicle_number",
        "registration_number",
        "bus_name",
        "vehicle_type",
        "seating_capacity",
        "status",
        "allocated_display",
        "available_display",
        "insurance_expiry",
        "fitness_expiry",
    ]
    list_filter = ["status", "vehicle_type"]
    search_fields = ["vehicle_number", "registration_number", "bus_name"]
    readonly_fields = ["created_at", "updated_at"]

    def allocated_display(self, obj):
        return obj.allocated_count
    allocated_display.short_description = "Allocated"

    def available_display(self, obj):
        return obj.available_seats
    available_display.short_description = "Available"


@admin.register(Route)
class RouteAdmin(admin.ModelAdmin):
    list_display = ["code", "name", "start_point", "destination", "assigned_vehicle", "is_active", "stops_count", "students_count"]
    list_filter = ["is_active"]
    search_fields = ["code", "name", "start_point", "destination"]
    inlines = [StopInline]

    def stops_count(self, obj):
        return obj.stop_count
    stops_count.short_description = "Stops"

    def students_count(self, obj):
        return obj.total_students
    students_count.short_description = "Active Students"


@admin.register(Stop)
class StopAdmin(admin.ModelAdmin):
    list_display = ["route", "stop_order", "stop_name", "pickup_time", "drop_time", "distance_km", "fare_amount", "is_active"]
    list_filter = ["route", "is_active"]
    search_fields = ["stop_name", "stop_code", "route__code", "route__name"]


@admin.register(Driver)
class DriverAdmin(admin.ModelAdmin):
    list_display = ["name", "employee_id", "phone", "licence_number", "licence_expiry", "assigned_vehicle", "is_active", "licence_status"]
    list_filter = ["is_active"]
    search_fields = ["name", "employee_id", "licence_number", "phone"]

    def licence_status(self, obj):
        if obj.is_licence_expired:
            return "EXPIRED"
        if obj.is_licence_expiring_soon:
            return "EXPIRING SOON"
        return "VALID"
    licence_status.short_description = "Licence Status"


@admin.register(Conductor)
class ConductorAdmin(admin.ModelAdmin):
    list_display = ["name", "employee_id", "phone", "assigned_vehicle", "assigned_route", "is_active"]
    list_filter = ["is_active"]
    search_fields = ["name", "employee_id", "phone"]


@admin.register(TransportStaff)
class TransportStaffAdmin(admin.ModelAdmin):
    list_display = ["user", "role", "phone", "is_active"]
    list_filter = ["role", "is_active"]
    search_fields = ["user__username", "user__first_name", "user__last_name", "phone"]


@admin.register(TransportApplication)
class TransportApplicationAdmin(admin.ModelAdmin):
    list_display = ["application_id", "student", "route", "stop", "academic_year", "status", "application_date"]
    list_filter = ["status", "academic_year", "route"]
    search_fields = ["application_id", "student__name", "student__roll_no", "parent_phone"]
    readonly_fields = ["application_id", "created_at", "updated_at"]


@admin.register(TransportAllocation)
class TransportAllocationAdmin(admin.ModelAdmin):
    list_display = ["allocation_id", "student", "vehicle", "route", "stop", "academic_year", "seat_number", "status", "start_date"]
    list_filter = ["status", "academic_year", "vehicle", "route"]
    search_fields = ["allocation_id", "student__name", "student__roll_no", "vehicle__vehicle_number", "route__code"]
    readonly_fields = ["allocation_id", "created_at", "updated_at"]


@admin.register(TransportPass)
class TransportPassAdmin(admin.ModelAdmin):
    list_display = ["pass_number", "student", "allocation", "issue_date", "expiry_date", "status", "is_valid_display"]
    list_filter = ["status", "academic_year"]
    search_fields = ["pass_number", "student__name", "student__roll_no"]
    readonly_fields = ["pass_number", "created_at", "updated_at"]

    def is_valid_display(self, obj):
        return obj.is_valid
    is_valid_display.boolean = True
    is_valid_display.short_description = "Valid"


@admin.register(TransportAttendance)
class TransportAttendanceAdmin(admin.ModelAdmin):
    list_display = ["date", "trip_type", "vehicle", "route", "student", "boarding_stop", "status", "marked_by"]
    list_filter = ["date", "trip_type", "status", "route", "vehicle"]
    search_fields = ["student__name", "student__roll_no", "vehicle__vehicle_number", "route__code"]
    date_hierarchy = "date"


@admin.register(VehicleMaintenance)
class VehicleMaintenanceAdmin(admin.ModelAdmin):
    list_display = ["vehicle", "maintenance_type", "service_date", "next_service_date", "service_provider", "cost", "status"]
    list_filter = ["status", "maintenance_type", "vehicle"]
    search_fields = ["vehicle__vehicle_number", "service_provider", "invoice_number", "description"]
    date_hierarchy = "service_date"


@admin.register(TransportComplaint)
class TransportComplaintAdmin(admin.ModelAdmin):
    list_display = ["complaint_id", "student", "category", "title", "priority", "status", "assigned_staff", "created_at"]
    list_filter = ["status", "priority", "category"]
    search_fields = ["complaint_id", "title", "description", "student__name", "student__roll_no"]
    readonly_fields = ["complaint_id", "created_at", "updated_at"]


@admin.register(TransportIncident)
class TransportIncidentAdmin(admin.ModelAdmin):
    list_display = ["incident_id", "date", "vehicle", "route", "severity", "status", "reported_by"]
    list_filter = ["severity", "status", "date"]
    search_fields = ["incident_id", "description", "action_taken", "vehicle__vehicle_number"]
    date_hierarchy = "date"
    readonly_fields = ["incident_id", "created_at", "updated_at"]
