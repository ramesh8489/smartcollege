from decimal import Decimal
from django.db.models import Sum, Q, Count
from django.utils import timezone
from fees.models import FeeRecord, FeePayment
from timetable.models import Notification
from .models import (
    Vehicle,
    Route,
    Stop,
    Driver,
    Conductor,
    TransportApplication,
    TransportAllocation,
    TransportPass,
    TransportAttendance,
    VehicleMaintenance,
    TransportComplaint,
    TransportIncident,
)


TRANSPORT_FEE_SUBTYPES = [
    ("Transport Regular Fee", "Transport Regular Fee"),
    ("Transport Annual Fee", "Transport Annual Fee"),
    ("Transport Semester Fee", "Transport Semester Fee"),
    ("Transport Special Route Fee", "Transport Special Route Fee"),
    ("Transport Pass Fee", "Transport Pass Fee"),
    ("Other Transport Fee", "Other Transport Fee"),
]


# ================================================================
# FEES INTEGRATION SERVICE
# ================================================================
def get_student_transport_fees(student):
    """
    Retrieves and aggregates all transport fee records for a student
    using the existing college Fees module (FeeRecord where fee_type='TRANSPORT').
    """
    records = list(
        FeeRecord.objects.filter(
            student=student,
            fee_type="TRANSPORT",
        ).prefetch_related("payments").order_by("-created_at")
    )

    total_fees = sum((r.amount for r in records), Decimal("0.00"))
    total_paid = sum((r.paid_amount for r in records), Decimal("0.00"))
    outstanding = max(total_fees - total_paid, Decimal("0.00"))

    if not records:
        status = "NO_FEES"
    elif outstanding <= Decimal("0.00"):
        status = "PAID"
    elif total_paid > Decimal("0.00"):
        status = "PARTIAL"
    else:
        status = "PENDING"

    all_payments = []
    for r in records:
        all_payments.extend(r.payments.all())

    return {
        "records": records,
        "payments": all_payments,
        "total_fees": total_fees,
        "total_paid": total_paid,
        "outstanding": outstanding,
        "status": status,
    }


def get_admin_transport_fees_summary(route_id=None, vehicle_id=None):
    """
    Institutional overview of transport fees collected, outstanding, and defaulters.
    """
    qs = FeeRecord.objects.filter(fee_type="TRANSPORT").select_related("student", "student__course")

    if route_id:
        student_ids = TransportAllocation.objects.filter(
            route_id=route_id,
            status="ACTIVE",
        ).values_list("student_id", flat=True)
        qs = qs.filter(student_id__in=student_ids)

    if vehicle_id:
        student_ids = TransportAllocation.objects.filter(
            vehicle_id=vehicle_id,
            status="ACTIVE",
        ).values_list("student_id", flat=True)
        qs = qs.filter(student_id__in=student_ids)

    records = list(qs.prefetch_related("payments").order_by("-created_at"))

    total_billed = sum((r.amount for r in records), Decimal("0.00"))
    total_paid = sum((r.paid_amount for r in records), Decimal("0.00"))
    total_outstanding = max(total_billed - total_paid, Decimal("0.00"))

    collection_rate = 0.0
    if total_billed > Decimal("0.00"):
        collection_rate = round(float((total_paid / total_billed) * 100), 1)

    dues_list = [r for r in records if r.balance_amount > Decimal("0.00")]

    return {
        "records": records,
        "total_billed": total_billed,
        "total_paid": total_paid,
        "total_outstanding": total_outstanding,
        "collection_rate": collection_rate,
        "dues_list": dues_list,
        "dues_count": len(dues_list),
    }


# ================================================================
# STUDENT SUMMARY SERVICE
# ================================================================
def get_student_transport_summary(student):
    """
    Compiles complete transport profile and operational metrics for a student:
    - Active allocation (vehicle, route, stop, times)
    - Active or latest transport pass
    - Transport fee status
    - Attendance summary
    - Complaint summary
    - Application history
    """
    allocation = (
        TransportAllocation.objects.filter(student=student, status="ACTIVE")
        .select_related("vehicle", "route", "stop")
        .first()
    )

    pass_obj = (
        TransportPass.objects.filter(student=student)
        .select_related("allocation", "allocation__vehicle", "allocation__route", "allocation__stop")
        .order_by("-issue_date")
        .first()
    )

    fees_summary = get_student_transport_fees(student)

    # Attendance
    attendance_qs = TransportAttendance.objects.filter(student=student)
    total_att = attendance_qs.count()
    present_count = attendance_qs.filter(status="PRESENT").count()
    absent_count = attendance_qs.filter(status="ABSENT").count()
    not_boarded_count = attendance_qs.filter(status="NOT_BOARDED").count()
    att_percentage = round((present_count / total_att * 100), 1) if total_att > 0 else None

    # Complaints
    complaints = list(TransportComplaint.objects.filter(student=student).order_by("-created_at"))
    open_complaints = [c for c in complaints if c.status in ("OPEN", "IN_PROGRESS")]

    # Applications
    applications = list(
        TransportApplication.objects.filter(student=student)
        .select_related("route", "stop")
        .order_by("-application_date")
    )
    pending_app = next((a for a in applications if a.status == "PENDING"), None)

    return {
        "allocation": allocation,
        "pass": pass_obj,
        "fees": fees_summary,
        "attendance": {
            "total": total_att,
            "present": present_count,
            "absent": absent_count,
            "not_boarded": not_boarded_count,
            "percentage": att_percentage,
            "recent": list(attendance_qs.select_related("route", "vehicle", "boarding_stop").order_by("-date")[:5]),
        },
        "complaints": {
            "total": len(complaints),
            "open": len(open_complaints),
            "resolved": len([c for c in complaints if c.status in ("RESOLVED", "CLOSED")]),
            "recent": complaints[:5],
        },
        "applications": {
            "total": len(applications),
            "pending": pending_app,
            "list": applications,
        },
    }


# ================================================================
# ADMIN DASHBOARD METRICS SERVICE
# ================================================================
def get_transport_admin_dashboard_metrics():
    """
    Computes institutional transport KPIs, occupancy analytics, maintenance alerts,
    and fee metrics for the transport management dashboard.
    """
    total_vehicles = Vehicle.objects.count()
    active_vehicles = Vehicle.objects.filter(status="ACTIVE").count()
    maintenance_vehicles = Vehicle.objects.filter(status="MAINTENANCE").count()

    total_routes = Route.objects.count()
    active_routes = Route.objects.filter(is_active=True).count()
    total_stops = Stop.objects.filter(is_active=True).count()

    total_drivers = Driver.objects.filter(is_active=True).count()
    total_conductors = Conductor.objects.filter(is_active=True).count()

    total_students = TransportAllocation.objects.filter(status="ACTIVE").count()
    pending_applications = TransportApplication.objects.filter(status="PENDING").count()
    active_passes = TransportPass.objects.filter(status="ACTIVE", expiry_date__gte=timezone.now().date()).count()

    # Maintenance alerts
    today = timezone.now().date()
    maintenance_window = today + timezone.timedelta(days=30)
    upcoming_maintenance = VehicleMaintenance.objects.filter(
        status="SCHEDULED",
        service_date__gte=today,
        service_date__lte=maintenance_window,
    ).count()

    vehicles_expiring_soon = 0
    for v in Vehicle.objects.all():
        if v.needs_attention:
            vehicles_expiring_soon += 1

    drivers_licence_alerts = 0
    for d in Driver.objects.filter(is_active=True):
        if d.is_licence_expired or d.is_licence_expiring_soon:
            drivers_licence_alerts += 1

    # Today's attendance
    today_attendance_qs = TransportAttendance.objects.filter(date=today)
    today_present = today_attendance_qs.filter(status="PRESENT").count()
    today_absent = today_attendance_qs.filter(status="ABSENT").count()

    # Complaints
    open_complaints = TransportComplaint.objects.filter(status__in=["OPEN", "IN_PROGRESS"]).count()

    # Fees summary
    fees_summary = get_admin_transport_fees_summary()

    # Route-wise Occupancy Roster
    routes_roster = []
    routes = Route.objects.filter(is_active=True).select_related("assigned_vehicle").prefetch_related("stops", "allocations")
    for r in routes:
        v = r.assigned_vehicle
        capacity = v.seating_capacity if v else 0
        allocated = r.allocations.filter(status="ACTIVE").count()
        avail = max(0, capacity - allocated) if v else 0
        occupancy_pct = round((allocated / capacity * 100), 1) if capacity > 0 else 0.0
        routes_roster.append({
            "route": r,
            "vehicle": v,
            "capacity": capacity,
            "allocated": allocated,
            "available": avail,
            "occupancy_pct": occupancy_pct,
            "stops_count": r.stops.filter(is_active=True).count(),
        })

    return {
        "total_vehicles": total_vehicles,
        "active_vehicles": active_vehicles,
        "maintenance_vehicles": maintenance_vehicles,
        "total_routes": total_routes,
        "active_routes": active_routes,
        "total_stops": total_stops,
        "total_drivers": total_drivers,
        "total_conductors": total_conductors,
        "total_students": total_students,
        "pending_applications": pending_applications,
        "active_passes": active_passes,
        "today_present": today_present,
        "today_absent": today_absent,
        "open_complaints": open_complaints,
        "upcoming_maintenance": upcoming_maintenance,
        "vehicles_expiring_soon": vehicles_expiring_soon,
        "drivers_licence_alerts": drivers_licence_alerts,
        "fees_summary": fees_summary,
        "routes_roster": routes_roster,
    }


# ================================================================
# NOTIFICATION DISPATCHERS
# ================================================================
def notify_transport_event(user, title, message, link="/transport/"):
    """Creates a notification record in the student's or staff's notification log."""
    if not user:
        return None
    try:
        return Notification.objects.create(
            recipient=user,
            title=title,
            message=message,
            link=link,
        )
    except Exception:
        return None
