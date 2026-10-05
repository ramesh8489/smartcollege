from decimal import Decimal
from django.db.models import Sum, Q
from django.utils import timezone
from fees.models import FeeRecord, FeePayment
from .models import (
    HostelAllocation,
    Hostel,
    HostelAttendance,
    HostelComplaint,
    HostelApplication,
    HostelNotice,
    HostelVisitor,
)


HOSTEL_FEE_SUBTYPES = [
    ("Hostel Admission Fee", "Hostel Admission Fee"),
    ("Hostel Rent", "Hostel Rent"),
    ("Mess Fee", "Mess Fee"),
    ("Maintenance Fee", "Maintenance Fee"),
    ("Security Deposit", "Security Deposit"),
    ("Other Hostel Fee", "Other Hostel Fee"),
]


def get_student_hostel_fees(student):
    """
    Retrieves and aggregates all hostel fee records for a given student
    using the existing college Fees module.
    """
    records = list(
        FeeRecord.objects.filter(
            student=student,
            fee_type="HOSTEL",
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

    return {
        "records": records,
        "total_fees": total_fees,
        "total_paid": total_paid,
        "outstanding": outstanding,
        "status": status,
    }


def get_admin_hostel_fees_summary(hostel_id=None):
    """
    Institutional overview of hostel fees collected, outstanding, and defaulters.
    """
    qs = FeeRecord.objects.filter(fee_type="HOSTEL").select_related("student", "student__course")

    if hostel_id:
        # Filter to students allocated in that hostel
        student_ids = HostelAllocation.objects.filter(
            hostel_id=hostel_id,
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


def get_student_hostel_summary(student):
    """
    Compiles complete hostel profile and operational metrics for a student:
    - Active allocation (hostel, block, floor, room, bed, dates)
    - Fees (total, paid, outstanding, status)
    - Attendance (total, present, absent, percentage)
    - Maintenance complaints (open, in progress, resolved)
    - Applications (pending, approved, rejected, latest)
    - Active hostel notices
    """
    if not student:
        return None

    # Current active allocation
    allocation = (
        HostelAllocation.objects.filter(student=student, status="ACTIVE")
        .select_related("hostel", "block", "floor", "room", "bed")
        .first()
    )

    # Fees summary
    fees_summary = get_student_hostel_fees(student)

    # Attendance summary
    att_qs = HostelAttendance.objects.filter(student=student)
    att_total = att_qs.count()
    att_present = att_qs.filter(status="PRESENT").count()
    att_absent = att_qs.filter(status="ABSENT").count()
    att_permission = att_qs.filter(status="PERMISSION").count()
    att_leave = att_qs.filter(status="LEAVE").count()
    att_percentage = round((att_present / att_total) * 100, 1) if att_total > 0 else None

    # Complaints summary
    comp_qs = HostelComplaint.objects.filter(student=student)
    comp_total = comp_qs.count()
    comp_open = comp_qs.filter(status="OPEN").count()
    comp_in_progress = comp_qs.filter(status__in=["ASSIGNED", "IN_PROGRESS"]).count()
    comp_resolved = comp_qs.filter(status__in=["RESOLVED", "CLOSED"]).count()
    comp_rejected = comp_qs.filter(status="REJECTED").count()
    recent_complaints = list(comp_qs.select_related("hostel", "room").order_by("-created_at")[:5])

    # Applications summary
    apps_qs = HostelApplication.objects.filter(student=student)
    apps_total = apps_qs.count()
    apps_pending = apps_qs.filter(status__in=["PENDING", "UNDER_REVIEW"]).count()
    apps_approved = apps_qs.filter(status="APPROVED").count()
    apps_rejected = apps_qs.filter(status="REJECTED").count()
    latest_application = apps_qs.order_by("-application_date").first()

    # Notices
    today = timezone.localdate()
    if allocation:
        notices_qs = HostelNotice.objects.filter(
            Q(hostel=allocation.hostel) | Q(hostel__isnull=True),
            is_active=True,
            publish_date__lte=today,
        ).filter(Q(expiry_date__isnull=True) | Q(expiry_date__gte=today)).order_by("-publish_date")[:5]
    else:
        notices_qs = HostelNotice.objects.filter(
            hostel__isnull=True,
            is_active=True,
            publish_date__lte=today,
        ).filter(Q(expiry_date__isnull=True) | Q(expiry_date__gte=today)).order_by("-publish_date")[:5]

    # Visitors summary
    visitors_qs = HostelVisitor.objects.filter(student=student)
    visitors_total = visitors_qs.count()
    visitors_pending = visitors_qs.filter(status="PENDING").count()
    visitors_approved = visitors_qs.filter(status="APPROVED").count()
    visitors_checked_in = visitors_qs.filter(status="CHECKED_IN").count()
    recent_visitors = list(visitors_qs.select_related("hostel").order_by("-visit_date", "-created_at")[:5])

    return {
        "allocation": allocation,
        "fees": fees_summary,
        "attendance": {
            "total": att_total,
            "present": att_present,
            "absent": att_absent,
            "permission": att_permission,
            "leave": att_leave,
            "percentage": att_percentage,
        },
        "complaints": {
            "total": comp_total,
            "open": comp_open,
            "in_progress": comp_in_progress,
            "resolved": comp_resolved,
            "rejected": comp_rejected,
            "recent": recent_complaints,
        },
        "applications": {
            "total": apps_total,
            "pending": apps_pending,
            "approved": apps_approved,
            "rejected": apps_rejected,
            "latest": latest_application,
        },
        "visitors": {
            "total": visitors_total,
            "pending": visitors_pending,
            "approved": visitors_approved,
            "checked_in": visitors_checked_in,
            "recent": recent_visitors,
        },
        "notices": list(notices_qs),
    }
