import json
import uuid
from decimal import Decimal

from django.shortcuts import render, redirect, get_object_or_404
from django.views import View
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.utils import timezone
from django.db import transaction
from django.db.models import Q, Count, Sum
from django.core.paginator import Paginator

from students.models import Student
from timetable.models import Notification
from fees.models import FeeRecord, FeePayment
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
from .forms import (
    HostelApplicationForm,
    ApplicationReviewForm,
    HostelAllocationForm,
    CheckInOutForm,
    HostelRoomTransferForm,
    HostelFeeDemandForm,
    HostelFeePaymentForm,
    StudentComplaintForm,
    AdminComplaintUpdateForm,
    HostelNoticeForm,
    StudentVisitorRequestForm,
    AdminVisitorUpdateForm,
)
from .services import (
    get_student_hostel_fees,
    get_admin_hostel_fees_summary,
    get_student_hostel_summary,
)


def get_user_assigned_hostel_ids(user):
    if not user or not user.is_authenticated:
        return []
    if user.is_superuser:
        return list(Hostel.objects.values_list("id", flat=True))
    hw_ids = list(HostelWarden.objects.filter(user=user, is_active=True).values_list("hostel_id", flat=True))
    hi_ids = list(Hostel.objects.filter(warden_incharge=user, is_active=True).values_list("id", flat=True))
    return list(set(hw_ids + hi_ids))


def is_warden_for_hostel(user, hostel):
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    hostel_id = hostel.id if hasattr(hostel, "id") else hostel
    return hostel_id in get_user_assigned_hostel_ids(user)


def _is_hostel_admin(user):
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    return len(get_user_assigned_hostel_ids(user)) > 0


class HostelHomeView(LoginRequiredMixin, View):
    def get(self, request):
        if _is_hostel_admin(request.user):
            return redirect("hostel:admin_dashboard")
        student = Student.objects.filter(user=request.user).first()
        if not student:
            messages.warning(request, "Student profile required to access the hostel portal.")
            return redirect("home")
        hostel_data = get_student_hostel_summary(student)
        return render(
            request,
            "hostel/student_portal.html",
            {
                "student": student,
                "hostel": hostel_data,
                "allocation": hostel_data["allocation"],
                "fees": hostel_data["fees"],
                "attendance": hostel_data["attendance"],
                "complaints": hostel_data["complaints"],
                "applications": hostel_data["applications"],
                "visitors": hostel_data.get("visitors"),
                "notices": hostel_data["notices"],
            },
        )


class HostelAdminDashboardView(LoginRequiredMixin, View):
    """
    Comprehensive institutional Hostel Dashboard displaying:
    - 10 KPI Cards: Hostels, Rooms, Beds, Occupied, Available, Occupancy %,
      Pending Apps, Active Residents, Open Complaints, Outstanding Fees.
    - 5 Real DB Charts: Hostel Occupancy, Room Availability, Application Status,
      Complaint Status & Categories, Attendance Distribution.
    - Scoped strictly to assigned hostels for Wardens; campus-wide for Superusers.
    """
    def get(self, request):
        if not _is_hostel_admin(request.user):
            messages.error(request, "Access restricted to authorized hostel administrative personnel and wardens.")
            return redirect("hostel:home")

        assigned_hostel_ids = get_user_assigned_hostel_ids(request.user)
        selected_hostel_id = request.GET.get("hostel")

        # Base querysets respecting warden scoping
        hostels_qs = Hostel.objects.filter(is_active=True)
        if not request.user.is_superuser:
            hostels_qs = hostels_qs.filter(id__in=assigned_hostel_ids)

        active_hostel = None
        if selected_hostel_id:
            try:
                selected_hostel_id = int(selected_hostel_id)
                if request.user.is_superuser or selected_hostel_id in assigned_hostel_ids:
                    active_hostel = hostels_qs.filter(id=selected_hostel_id).first()
            except (ValueError, TypeError):
                selected_hostel_id = None

        if active_hostel:
            scoped_hostels = hostels_qs.filter(id=active_hostel.id)
            rooms_qs = HostelRoom.objects.filter(hostel=active_hostel, is_active=True)
            beds_qs = HostelBed.objects.filter(room__hostel=active_hostel, is_active=True)
            allocations_qs = HostelAllocation.objects.filter(hostel=active_hostel)
            applications_qs = HostelApplication.objects.filter(hostel_preference=active_hostel)
            complaints_qs = HostelComplaint.objects.filter(hostel=active_hostel)
            attendance_qs = HostelAttendance.objects.filter(hostel=active_hostel)
            fees_summary = get_admin_hostel_fees_summary(hostel_id=active_hostel.id)
        else:
            scoped_hostels = hostels_qs
            if request.user.is_superuser:
                rooms_qs = HostelRoom.objects.filter(is_active=True)
                beds_qs = HostelBed.objects.filter(is_active=True)
                allocations_qs = HostelAllocation.objects.all()
                applications_qs = HostelApplication.objects.all()
                complaints_qs = HostelComplaint.objects.all()
                attendance_qs = HostelAttendance.objects.all()
                fees_summary = get_admin_hostel_fees_summary()
            else:
                rooms_qs = HostelRoom.objects.filter(hostel_id__in=assigned_hostel_ids, is_active=True)
                beds_qs = HostelBed.objects.filter(room__hostel_id__in=assigned_hostel_ids, is_active=True)
                allocations_qs = HostelAllocation.objects.filter(hostel_id__in=assigned_hostel_ids)
                applications_qs = HostelApplication.objects.filter(hostel_preference_id__in=assigned_hostel_ids)
                complaints_qs = HostelComplaint.objects.filter(hostel_id__in=assigned_hostel_ids)
                attendance_qs = HostelAttendance.objects.filter(hostel_id__in=assigned_hostel_ids)
                fees_summary = get_admin_hostel_fees_summary()

        # 10 Metric Cards (Aggregated with minimal DB roundtrips)
        total_hostels = scoped_hostels.count()
        total_rooms = rooms_qs.count()

        bed_aggregates = beds_qs.aggregate(
            total=Count("id"),
            occupied=Count("id", filter=Q(status="OCCUPIED")),
            available=Count("id", filter=Q(status="AVAILABLE")),
            maintenance=Count("id", filter=Q(status="MAINTENANCE")),
        )
        total_beds = bed_aggregates["total"]
        occupied_beds = bed_aggregates["occupied"]
        available_beds = bed_aggregates["available"]
        maintenance_beds = bed_aggregates["maintenance"]
        occupancy_rate = round((occupied_beds / total_beds * 100), 1) if total_beds > 0 else 0.0

        pending_applications = applications_qs.filter(status__in=["PENDING", "UNDER_REVIEW"]).count()
        active_residents = allocations_qs.filter(status="ACTIVE").count()
        open_complaints = complaints_qs.filter(status__in=["OPEN", "ASSIGNED", "IN_PROGRESS"]).count()
        outstanding_fees = fees_summary["total_outstanding"]

        # 1. Chart Data: Hostel Occupancy (annotated in single query to eliminate N+1)
        scoped_hostels_annotated = scoped_hostels.annotate(
            annotated_rooms=Count("rooms", filter=Q(rooms__is_active=True), distinct=True),
            annotated_total_beds=Count("rooms__beds", filter=Q(rooms__beds__is_active=True), distinct=True),
            annotated_occupied_beds=Count(
                "rooms__beds",
                filter=Q(rooms__beds__is_active=True, rooms__beds__status="OCCUPIED"),
                distinct=True,
            ),
            annotated_available_beds=Count(
                "rooms__beds",
                filter=Q(rooms__beds__is_active=True, rooms__beds__status="AVAILABLE"),
                distinct=True,
            ),
        )

        hostel_chart_labels = []
        hostel_chart_occupied = []
        hostel_chart_available = []
        hostel_table_data = []
        for h in scoped_hostels_annotated:
            h_tot = h.annotated_total_beds
            h_occ = h.annotated_occupied_beds
            h_avail = h.annotated_available_beds
            h_pct = round((h_occ / h_tot * 100), 1) if h_tot > 0 else 0.0
            hostel_chart_labels.append(h.code or h.name[:15])
            hostel_chart_occupied.append(h_occ)
            hostel_chart_available.append(h_avail)
            hostel_table_data.append({
                "hostel": h,
                "total_rooms": h.annotated_rooms,
                "total_beds": h_tot,
                "occupied_beds": h_occ,
                "available_beds": h_avail,
                "occupancy_rate": h_pct,
            })

        # 2. Chart Data: Room Availability (aggregated in 1 query)
        ROOM_TYPES = [
            ("SINGLE", "Single"),
            ("DOUBLE", "Double"),
            ("TRIPLE", "Triple"),
            ("FOUR_SHARING", "4-Sharing"),
            ("DORMITORY", "Dormitory"),
            ("OTHER", "Other"),
        ]
        room_type_labels = [rt[1] for rt in ROOM_TYPES]
        bed_stats = beds_qs.values("room__room_type", "status").annotate(count=Count("id"))
        bed_stats_map = {(bs["room__room_type"], bs["status"]): bs["count"] for bs in bed_stats}
        room_type_occupied = [bed_stats_map.get((rt[0], "OCCUPIED"), 0) for rt in ROOM_TYPES]
        room_type_available = [bed_stats_map.get((rt[0], "AVAILABLE"), 0) for rt in ROOM_TYPES]

        # 3. Chart Data: Application Status (aggregated in 1 query)
        app_status_labels = ["Pending", "Under Review", "Approved", "Rejected", "Waitlisted", "Cancelled"]
        app_status_map = dict(applications_qs.values_list("status").annotate(count=Count("id")))
        app_status_counts = [
            app_status_map.get("PENDING", 0),
            app_status_map.get("UNDER_REVIEW", 0),
            app_status_map.get("APPROVED", 0),
            app_status_map.get("REJECTED", 0),
            app_status_map.get("WAITLISTED", 0),
            app_status_map.get("CANCELLED", 0),
        ]

        # 4. Chart Data: Complaint Status & Category (aggregated in 2 queries)
        complaint_status_labels = ["Open", "Assigned", "In Progress", "Resolved", "Closed", "Rejected"]
        complaint_status_map = dict(complaints_qs.values_list("status").annotate(count=Count("id")))
        complaint_status_counts = [
            complaint_status_map.get("OPEN", 0),
            complaint_status_map.get("ASSIGNED", 0),
            complaint_status_map.get("IN_PROGRESS", 0),
            complaint_status_map.get("RESOLVED", 0),
            complaint_status_map.get("CLOSED", 0),
            complaint_status_map.get("REJECTED", 0),
        ]

        COMPLAINT_CATS = [
            ("ELECTRICAL", "Electrical"),
            ("PLUMBING", "Plumbing"),
            ("FURNITURE", "Furniture"),
            ("INTERNET", "Internet"),
            ("CLEANING", "Cleaning"),
            ("WATER", "Water"),
            ("ROOM", "Room"),
            ("OTHER", "Other"),
        ]
        complaint_cat_labels = [c[1] for c in COMPLAINT_CATS]
        complaint_cat_map = dict(complaints_qs.values_list("category").annotate(count=Count("id")))
        complaint_cat_counts = [complaint_cat_map.get(c[0], 0) for c in COMPLAINT_CATS]

        # 5. Chart Data: Attendance Distribution (aggregated in 1 query)
        att_status_labels = ["Present", "Absent", "Permission", "Leave"]
        att_status_map = dict(attendance_qs.values_list("status").annotate(count=Count("id")))
        att_status_counts = [
            att_status_map.get("PRESENT", 0),
            att_status_map.get("ABSENT", 0),
            att_status_map.get("PERMISSION", 0),
            att_status_map.get("LEAVE", 0),
        ]

        # Recent activities (optimized with select_related)
        recent_applications = list(applications_qs.select_related("student", "hostel_preference").order_by("-application_date")[:5])
        recent_complaints = list(complaints_qs.select_related("student", "hostel", "room").order_by("-created_at")[:5])
        recent_allocations = list(allocations_qs.select_related("student", "hostel", "room", "bed").order_by("-created_at")[:5])

        context = {
            "all_hostels": hostels_qs,
            "active_hostel": active_hostel,
            "kpi": {
                "total_hostels": total_hostels,
                "total_rooms": total_rooms,
                "total_beds": total_beds,
                "occupied_beds": occupied_beds,
                "available_beds": available_beds,
                "maintenance_beds": maintenance_beds,
                "occupancy_rate": occupancy_rate,
                "pending_applications": pending_applications,
                "active_residents": active_residents,
                "open_complaints": open_complaints,
                "outstanding_fees": outstanding_fees,
                "total_fees_billed": fees_summary["total_billed"],
                "total_fees_paid": fees_summary["total_paid"],
            },
            "hostel_table_data": hostel_table_data,
            "recent_applications": recent_applications,
            "recent_complaints": recent_complaints,
            "recent_allocations": recent_allocations,
            "chart_hostel_occupancy": json.dumps({
                "labels": hostel_chart_labels,
                "occupied": hostel_chart_occupied,
                "available": hostel_chart_available,
            }),
            "chart_room_availability": json.dumps({
                "labels": room_type_labels,
                "occupied": room_type_occupied,
                "available": room_type_available,
            }),
            "chart_application_status": json.dumps({
                "labels": app_status_labels,
                "counts": app_status_counts,
            }),
            "chart_complaint_status": json.dumps({
                "labels": complaint_status_labels,
                "counts": complaint_status_counts,
                "cat_labels": complaint_cat_labels,
                "cat_counts": complaint_cat_counts,
            }),
            "chart_attendance": json.dumps({
                "labels": att_status_labels,
                "counts": att_status_counts,
            }),
        }
        return render(request, "hostel/admin_dashboard.html", context)


class HostelRoomSearchView(LoginRequiredMixin, View):
    """
    Phase 12: Room Availability & Search View.
    Allows administrators and wardens to filter and search rooms by:
    - Hostel
    - Block
    - Floor
    - Room type
    - Minimum available beds
    - Room status
    Displays only beds that can actually be allocated, along with occupied/available counts,
    and supports pagination.
    """
    def get(self, request):
        if not _is_hostel_admin(request.user):
            messages.error(request, "Access restricted to authorized hostel administrative personnel and wardens.")
            return redirect("hostel:home")

        assigned_hostel_ids = get_user_assigned_hostel_ids(request.user)

        # Scoped hostels
        hostels_qs = Hostel.objects.filter(is_active=True)
        if not request.user.is_superuser:
            hostels_qs = hostels_qs.filter(id__in=assigned_hostel_ids)

        # Query parameters
        hostel_id = request.GET.get("hostel", "").strip()
        block_id = request.GET.get("block", "").strip()
        floor_id = request.GET.get("floor", "").strip()
        room_type = request.GET.get("room_type", "").strip()
        status_val = request.GET.get("status", "").strip()
        min_available = request.GET.get("min_available", "").strip()
        search_query = request.GET.get("q", "").strip()

        rooms_qs = HostelRoom.objects.filter(is_active=True).select_related("hostel", "block", "floor")
        if not request.user.is_superuser:
            rooms_qs = rooms_qs.filter(hostel_id__in=assigned_hostel_ids)

        if hostel_id:
            try:
                h_id = int(hostel_id)
                if request.user.is_superuser or h_id in assigned_hostel_ids:
                    rooms_qs = rooms_qs.filter(hostel_id=h_id)
            except ValueError:
                pass

        if block_id:
            try:
                b_id = int(block_id)
                rooms_qs = rooms_qs.filter(block_id=b_id)
            except ValueError:
                rooms_qs = rooms_qs.filter(block__name__icontains=block_id)

        if floor_id:
            try:
                f_id = int(floor_id)
                rooms_qs = rooms_qs.filter(floor_id=f_id)
            except ValueError:
                rooms_qs = rooms_qs.filter(floor__name__icontains=floor_id)

        if room_type:
            rooms_qs = rooms_qs.filter(room_type=room_type)

        if status_val:
            rooms_qs = rooms_qs.filter(status=status_val)

        if search_query:
            rooms_qs = rooms_qs.filter(
                Q(room_number__icontains=search_query) |
                Q(block__name__icontains=search_query) |
                Q(hostel__name__icontains=search_query) |
                Q(hostel__code__icontains=search_query)
            )

        # Annotate bed counts from actual DB beds
        rooms_qs = rooms_qs.annotate(
            num_available_beds=Count("beds", filter=Q(beds__status="AVAILABLE", beds__is_active=True)),
            num_occupied_beds=Count("beds", filter=Q(beds__status="OCCUPIED", beds__is_active=True)),
            num_total_beds=Count("beds", filter=Q(beds__is_active=True)),
        ).prefetch_related(
            "beds"
        ).order_by("hostel__name", "block__name", "floor__floor_number", "room_number")

        if min_available:
            try:
                min_avail_int = int(min_available)
                if min_avail_int > 0:
                    rooms_qs = rooms_qs.filter(num_available_beds__gte=min_avail_int)
            except ValueError:
                pass

        # Blocks and floors for filter dropdowns
        scoped_blocks = HostelBlock.objects.filter(hostel__in=hostels_qs, is_active=True)
        scoped_floors = HostelFloor.objects.filter(block__in=scoped_blocks, is_active=True)
        if hostel_id and hostel_id.isdigit():
            scoped_blocks = scoped_blocks.filter(hostel_id=int(hostel_id))
            scoped_floors = scoped_floors.filter(block__hostel_id=int(hostel_id))

        # Overall summary stats for filtered rooms
        total_rooms_count = rooms_qs.count()
        total_avail_beds_count = sum(r.num_available_beds for r in rooms_qs)
        total_occ_beds_count = sum(r.num_occupied_beds for r in rooms_qs)

        # Pagination: 15 rooms per page
        paginator = Paginator(rooms_qs, 15)
        page_number = request.GET.get("page", 1)
        page_obj = paginator.get_page(page_number)

        # Attach only beds that can actually be allocated
        for room in page_obj.object_list:
            room.allocatable_beds = [b for b in room.beds.all() if b.is_active and b.status == "AVAILABLE"]

        # Preserve query params for pagination
        params = request.GET.copy()
        if "page" in params:
            del params["page"]
        query_string = params.urlencode()

        context = {
            "page_obj": page_obj,
            "rooms": page_obj.object_list,
            "hostels_list": hostels_qs,
            "blocks_list": scoped_blocks,
            "floors_list": scoped_floors,
            "room_types": HostelRoom.ROOM_TYPE_CHOICES,
            "room_statuses": HostelRoom.ROOM_STATUS_CHOICES,
            "selected_hostel": hostel_id,
            "selected_block": block_id,
            "selected_floor": floor_id,
            "selected_room_type": room_type,
            "selected_status": status_val,
            "selected_min_available": min_available,
            "search_query": search_query,
            "total_rooms_count": total_rooms_count,
            "total_avail_beds_count": total_avail_beds_count,
            "total_occ_beds_count": total_occ_beds_count,
            "query_string": query_string,
        }
        return render(request, "hostel/room_search.html", context)


class ApplicationListView(LoginRequiredMixin, View):
    def get(self, request):
        student = Student.objects.filter(user=request.user).first()
        if not student:
            if _is_hostel_admin(request.user):
                return redirect("hostel:admin_applications")
            messages.warning(request, "Student profile required to view hostel applications.")
            return redirect("home")

        applications = HostelApplication.objects.filter(student=student).select_related(
            "hostel_preference", "reviewed_by"
        )
        return render(
            request,
            "hostel/application_list.html",
            {
                "applications": applications,
                "student": student,
            },
        )


class ApplicationCreateView(LoginRequiredMixin, View):
    def get(self, request):
        student = Student.objects.filter(user=request.user).first()
        if not student:
            messages.error(request, "Only registered students can apply for hostel accommodation.")
            return redirect("home")

        # Check if student already has a pending application
        existing_pending = HostelApplication.objects.filter(
            student=student,
            status__in=["PENDING", "UNDER_REVIEW", "APPROVED"],
        ).first()
        if existing_pending:
            messages.info(
                request,
                f"You already have an active application ({existing_pending.application_id}) with status '{existing_pending.get_status_display()}'.",
            )
            return redirect("hostel:application_detail", pk=existing_pending.pk)

        form = HostelApplicationForm()
        return render(request, "hostel/application_form.html", {"form": form, "student": student})

    def post(self, request):
        student = Student.objects.filter(user=request.user).first()
        if not student:
            raise PermissionDenied("Only registered students can submit hostel applications.")

        existing_pending = HostelApplication.objects.filter(
            student=student,
            status__in=["PENDING", "UNDER_REVIEW", "APPROVED"],
        ).first()
        if existing_pending:
            messages.warning(request, "You already have an active application.")
            return redirect("hostel:application_detail", pk=existing_pending.pk)

        form = HostelApplicationForm(request.POST)
        if form.is_valid():
            application = form.save(commit=False)
            application.student = student
            application.save()
            if student.user:
                Notification.objects.create(
                    recipient=student.user,
                    title="Hostel Application Submitted",
                    message=f"Your application {application.application_id} for {application.hostel_preference.name} was successfully submitted.",
                    link=f"/hostel/applications/{application.pk}/",
                )
            messages.success(
                request,
                f"Hostel Application {application.application_id} submitted successfully! It is now pending administrative review.",
            )
            return redirect("hostel:application_detail", pk=application.pk)

        return render(request, "hostel/application_form.html", {"form": form, "student": student})


class ApplicationDetailView(LoginRequiredMixin, View):
    def get(self, request, pk):
        application = get_object_or_404(
            HostelApplication.objects.select_related("student", "hostel_preference", "reviewed_by"),
            pk=pk,
        )
        is_owner = application.student.user_id == request.user.id
        is_warden = is_warden_for_hostel(request.user, application.hostel_preference)
        can_access = request.user.is_superuser or is_warden or is_owner

        if not can_access:
            raise PermissionDenied("You are not authorized to view this hostel application.")

        review_form = ApplicationReviewForm() if (request.user.is_superuser or is_warden) else None
        return render(
            request,
            "hostel/application_detail.html",
            {
                "application": application,
                "is_admin": (request.user.is_superuser or is_warden),
                "review_form": review_form,
            },
        )


class AdminApplicationListView(LoginRequiredMixin, UserPassesTestMixin, View):
    def test_func(self):
        return _is_hostel_admin(self.request.user)

    def get(self, request):
        status_filter = request.GET.get("status", "")
        hostel_filter = request.GET.get("hostel", "")
        q = request.GET.get("q", "").strip()

        qs = HostelApplication.objects.select_related("student", "hostel_preference", "reviewed_by")

        # If user is warden only, scope to their managed hostels
        if not request.user.is_superuser:
            assigned_ids = get_user_assigned_hostel_ids(request.user)
            qs = qs.filter(hostel_preference_id__in=assigned_ids)

        if status_filter:
            qs = qs.filter(status=status_filter)
        if hostel_filter:
            qs = qs.filter(hostel_preference_id=hostel_filter)
        if q:
            qs = qs.filter(
                Q(student__name__icontains=q)
                | Q(student__roll_no__icontains=q)
                | Q(application_id__icontains=q)
            )

        paginator = Paginator(qs, 20)
        page_number = request.GET.get("page")
        page_obj = paginator.get_page(page_number)

        if not request.user.is_superuser:
            assigned_ids = get_user_assigned_hostel_ids(request.user)
            hostels = Hostel.objects.filter(id__in=assigned_ids, is_active=True)
        else:
            hostels = Hostel.objects.filter(is_active=True)
        return render(
            request,
            "hostel/admin_application_list.html",
            {
                "page_obj": page_obj,
                "hostels": hostels,
                "status_filter": status_filter,
                "hostel_filter": hostel_filter,
                "q": q,
                "status_choices": HostelApplication.STATUS_CHOICES,
            },
        )


class AdminApplicationReviewView(LoginRequiredMixin, UserPassesTestMixin, View):
    def test_func(self):
        return _is_hostel_admin(self.request.user)

    def post(self, request, pk):
        application = get_object_or_404(
            HostelApplication.objects.select_related("student", "hostel_preference"),
            pk=pk,
        )
        if not is_warden_for_hostel(request.user, application.hostel_preference):
            raise PermissionDenied("You are not the assigned warden for this hostel.")

        form = ApplicationReviewForm(request.POST)
        if form.is_valid():
            action = form.cleaned_data["action"]
            remarks = form.cleaned_data["remarks"]
            rejection_reason = form.cleaned_data["rejection_reason"]

            application.status = action
            application.remarks = remarks
            application.reviewed_by = request.user
            application.reviewed_date = timezone.now()
            if action == "REJECTED":
                application.rejection_reason = rejection_reason
            else:
                application.rejection_reason = ""
            application.save()

            if application.student and application.student.user:
                if action == "APPROVED":
                    Notification.objects.create(
                        recipient=application.student.user,
                        title="Hostel Application Approved",
                        message=f"Congratulations! Your hostel application {application.application_id} for {application.hostel_preference.name} has been approved.",
                        link=f"/hostel/applications/{application.pk}/",
                    )
                elif action == "REJECTED":
                    Notification.objects.create(
                        recipient=application.student.user,
                        title="Hostel Application Rejected",
                        message=f"Your hostel application {application.application_id} for {application.hostel_preference.name} was rejected. Reason: {application.rejection_reason or 'No reason provided'}",
                        link=f"/hostel/applications/{application.pk}/",
                    )
                elif action == "WAITLISTED":
                    Notification.objects.create(
                        recipient=application.student.user,
                        title="Hostel Application Waitlisted",
                        message=f"Your hostel application {application.application_id} has been moved to waitlisted status.",
                        link=f"/hostel/applications/{application.pk}/",
                    )

            messages.success(
                request,
                f"Application {application.application_id} has been marked as '{application.get_status_display()}'.",
            )
            return redirect("hostel:application_detail", pk=application.pk)

        # Form has validation errors (e.g. rejection without reason)
        return render(
            request,
            "hostel/application_detail.html",
            {
                "application": application,
                "is_admin": True,
                "review_form": form,
            },
        )


class AdminAllocationListView(LoginRequiredMixin, UserPassesTestMixin, View):
    def test_func(self):
        return _is_hostel_admin(self.request.user)

    def get(self, request):
        hostel_filter = request.GET.get("hostel", "")
        status_filter = request.GET.get("status", "ACTIVE")
        q = request.GET.get("q", "").strip()

        qs = HostelAllocation.objects.select_related(
            "student", "hostel", "block", "floor", "room", "bed", "allocated_by"
        )

        if not request.user.is_superuser:
            assigned_ids = get_user_assigned_hostel_ids(request.user)
            qs = qs.filter(hostel_id__in=assigned_ids)

        if hostel_filter:
            qs = qs.filter(hostel_id=hostel_filter)
        if status_filter:
            qs = qs.filter(status=status_filter)
        if q:
            qs = qs.filter(
                Q(student__name__icontains=q)
                | Q(student__roll_no__icontains=q)
                | Q(room__room_number__icontains=q)
                | Q(bed__bed_number__icontains=q)
                | Q(allocation_id__icontains=q)
            )

        paginator = Paginator(qs, 20)
        page_number = request.GET.get("page")
        page_obj = paginator.get_page(page_number)

        if not request.user.is_superuser:
            assigned_ids = get_user_assigned_hostel_ids(request.user)
            hostels = Hostel.objects.filter(id__in=assigned_ids, is_active=True)
        else:
            hostels = Hostel.objects.filter(is_active=True)
        return render(
            request,
            "hostel/admin_allocation_list.html",
            {
                "page_obj": page_obj,
                "hostels": hostels,
                "hostel_filter": hostel_filter,
                "status_filter": status_filter,
                "q": q,
                "status_choices": HostelAllocation.STATUS_CHOICES,
            },
        )


class AdminAllocationCreateView(LoginRequiredMixin, UserPassesTestMixin, View):
    def test_func(self):
        return _is_hostel_admin(self.request.user)

    def get(self, request):
        initial = {}
        student_id = request.GET.get("student")
        app_id = request.GET.get("app")
        if student_id:
            initial["student"] = student_id
        if app_id:
            app = HostelApplication.objects.filter(pk=app_id).first()
            if app:
                initial["student"] = app.student_id
                initial["hostel"] = app.hostel_preference_id
                initial["academic_year"] = app.academic_year

        form = HostelAllocationForm(initial=initial)
        rooms = HostelRoom.objects.filter(is_active=True).exclude(status__in=["FULL", "MAINTENANCE", "INACTIVE"]).select_related("hostel", "block")
        return render(request, "hostel/admin_allocation_form.html", {"form": form, "rooms": rooms})

    def post(self, request):
        form = HostelAllocationForm(request.POST)
        if form.is_valid():
            allocation = form.save(commit=False)
            allocation.block = allocation.room.block
            allocation.floor = allocation.room.floor
            allocation.allocated_by = request.user
            try:
                allocation.full_clean()
                allocation.save()
                # Update any pending application for this student
                HostelApplication.objects.filter(
                    student=allocation.student,
                    status__in=["PENDING", "UNDER_REVIEW", "WAITLISTED"],
                ).update(status="APPROVED", reviewed_by=request.user, reviewed_date=timezone.now())

                if allocation.student and allocation.student.user:
                    Notification.objects.create(
                        recipient=allocation.student.user,
                        title="Hostel Allocation Completed",
                        message=f"You have been allocated Bed {allocation.bed.bed_number} in Room {allocation.room.room_number}, {allocation.hostel.name}.",
                        link="/hostel/",
                    )

                messages.success(
                    request,
                    f"Successfully allocated {allocation.student.name} to Room {allocation.room.room_number}, Bed {allocation.bed.bed_number} (ID: {allocation.allocation_id})!",
                )
                return redirect("hostel:admin_allocation_detail", pk=allocation.pk)
            except Exception as e:
                messages.error(request, f"Allocation failed: {e}")
        else:
            messages.error(request, "Please correct the form errors below.")

        rooms = HostelRoom.objects.filter(is_active=True).exclude(status__in=["FULL", "MAINTENANCE", "INACTIVE"]).select_related("hostel", "block")
        return render(request, "hostel/admin_allocation_form.html", {"form": form, "rooms": rooms})


class AdminAllocationDetailView(LoginRequiredMixin, UserPassesTestMixin, View):
    def test_func(self):
        return _is_hostel_admin(self.request.user)

    def get(self, request, pk):
        allocation = get_object_or_404(
            HostelAllocation.objects.select_related(
                "student", "hostel", "block", "floor", "room", "bed", "allocated_by"
            ),
            pk=pk,
        )
        if not is_warden_for_hostel(request.user, allocation.hostel):
            raise PermissionDenied("You are not authorized to view allocations for this hostel.")

        lifecycle_events = allocation.lifecycle_events.select_related("processed_by").order_by("-event_date", "-created_at")
        transfers = allocation.transfers.select_related(
            "old_hostel", "old_room", "old_bed", "new_hostel", "new_room", "new_bed", "approved_by"
        ).order_by("-transfer_date", "-created_at")
        checkin_form = CheckInOutForm(initial={"event_type": "CHECK_IN", "event_date": timezone.now().date()})
        checkout_form = CheckInOutForm(initial={"event_type": "CHECK_OUT", "event_date": timezone.now().date()})
        return render(
            request,
            "hostel/admin_allocation_detail.html",
            {
                "allocation": allocation,
                "lifecycle_events": lifecycle_events,
                "transfers": transfers,
                "checkin_form": checkin_form,
                "checkout_form": checkout_form,
            },
        )


class ProcessCheckInOutView(LoginRequiredMixin, UserPassesTestMixin, View):
    def test_func(self):
        return _is_hostel_admin(self.request.user)

    def post(self, request, pk):
        allocation = get_object_or_404(
            HostelAllocation.objects.select_related("student", "hostel", "room", "bed"),
            pk=pk,
        )
        if not is_warden_for_hostel(request.user, allocation.hostel):
            raise PermissionDenied("You are not authorized to process check-in/out for this hostel.")

        form = CheckInOutForm(request.POST)
        if form.is_valid():
            event = form.save(commit=False)
            event.allocation = allocation
            event.student = allocation.student
            event.processed_by = request.user
            event.save()
            action_label = "Checked In" if event.event_type == "CHECK_IN" else "Checked Out"

            if allocation.student and allocation.student.user:
                if event.event_type == "CHECK_IN":
                    Notification.objects.create(
                        recipient=allocation.student.user,
                        title="Hostel Check-in Completed",
                        message=f"Your check-in at {allocation.hostel.name} (Room {allocation.room.room_number}, Bed {allocation.bed.bed_number}) on {event.event_date.strftime('%d-%m-%Y')} has been confirmed.",
                        link="/hostel/",
                    )
                else:
                    Notification.objects.create(
                        recipient=allocation.student.user,
                        title="Hostel Check-out Completed",
                        message=f"Your check-out from {allocation.hostel.name} (Room {allocation.room.room_number}, Bed {allocation.bed.bed_number}) on {event.event_date.strftime('%d-%m-%Y')} has been recorded.",
                        link="/hostel/",
                    )

            messages.success(
                request,
                f"Student {allocation.student.name} successfully {action_label}! Bed {allocation.bed.bed_number} status updated.",
            )
        else:
            for field, errs in form.errors.items():
                for err in errs:
                    messages.error(request, f"{field.title()}: {err}")

        return redirect("hostel:admin_allocation_detail", pk=allocation.pk)


class AdminRoomTransferView(LoginRequiredMixin, UserPassesTestMixin, View):
    def test_func(self):
        return _is_hostel_admin(self.request.user)

    def get(self, request, pk):
        allocation = get_object_or_404(
            HostelAllocation.objects.select_related("student", "hostel", "block", "floor", "room", "bed"),
            pk=pk,
        )
        if not is_warden_for_hostel(request.user, allocation.hostel):
            raise PermissionDenied("You are not authorized to transfer residents of this hostel.")

        if allocation.status != "ACTIVE":
            messages.warning(request, f"Cannot transfer an allocation with status '{allocation.get_status_display()}'.")
            return redirect("hostel:admin_allocation_detail", pk=allocation.pk)

        form = HostelRoomTransferForm(initial={"transfer_date": timezone.now().date(), "new_hostel": allocation.hostel})
        return render(
            request,
            "hostel/admin_transfer_form.html",
            {
                "allocation": allocation,
                "form": form,
            },
        )

    def post(self, request, pk):
        allocation = get_object_or_404(
            HostelAllocation.objects.select_related("student", "hostel", "block", "floor", "room", "bed"),
            pk=pk,
        )
        if not is_warden_for_hostel(request.user, allocation.hostel):
            raise PermissionDenied("You are not authorized to transfer residents of this hostel.")
        if allocation.status != "ACTIVE":
            messages.error(request, "Only active residents can be transferred.")
            return redirect("hostel:admin_allocation_detail", pk=allocation.pk)

        form = HostelRoomTransferForm(request.POST)
        if form.is_valid():
            new_hostel = form.cleaned_data["new_hostel"]
            new_room = form.cleaned_data["new_room"]
            new_bed = form.cleaned_data["new_bed"]
            transfer_date = form.cleaned_data["transfer_date"]
            reason = form.cleaned_data["reason"]
            remarks = form.cleaned_data["remarks"]

            if new_bed.id == allocation.bed_id:
                messages.error(request, "Destination bed cannot be the same as current bed.")
                return render(request, "hostel/admin_transfer_form.html", {"allocation": allocation, "form": form})

            transfer = HostelRoomTransfer(
                student=allocation.student,
                allocation=allocation,
                old_hostel=allocation.hostel,
                old_block=allocation.block,
                old_floor=allocation.floor,
                old_room=allocation.room,
                old_bed=allocation.bed,
                new_hostel=new_hostel,
                new_block=new_room.block,
                new_floor=new_room.floor,
                new_room=new_room,
                new_bed=new_bed,
                transfer_date=transfer_date,
                reason=reason,
                approved_by=request.user,
                remarks=remarks,
            )
            transfer.save()

            if allocation.student and allocation.student.user:
                Notification.objects.create(
                    recipient=allocation.student.user,
                    title="Hostel Room Transfer Completed",
                    message=f"Your room transfer has been finalized: moved from {transfer.old_room.room_number}/{transfer.old_bed.bed_number} to {transfer.new_room.room_number}/{transfer.new_bed.bed_number} ({transfer.new_hostel.name}).",
                    link="/hostel/",
                )

            messages.success(
                request,
                f"Successfully transferred {allocation.student.name} from Room {transfer.old_room.room_number}/{transfer.old_bed.bed_number} to Room {transfer.new_room.room_number}/{transfer.new_bed.bed_number}!",
            )
            return redirect("hostel:admin_allocation_detail", pk=allocation.pk)

        return render(request, "hostel/admin_transfer_form.html", {"allocation": allocation, "form": form})


class AdminHostelFeeListView(LoginRequiredMixin, UserPassesTestMixin, View):
    def test_func(self):
        return _is_hostel_admin(self.request.user)

    def get(self, request):
        hostel_id = request.GET.get("hostel")
        status_filter = request.GET.get("status")
        search_query = request.GET.get("search", "").strip()

        summary = get_admin_hostel_fees_summary(hostel_id=hostel_id if hostel_id else None)
        records = summary["records"]

        if status_filter in ["PENDING", "PARTIAL", "PAID"]:
            records = [r for r in records if r.status == status_filter]

        if search_query:
            q_lower = search_query.lower()
            records = [
                r for r in records
                if q_lower in r.student.name.lower()
                or (r.student.roll_no and q_lower in r.student.roll_no.lower())
                or q_lower in r.title.lower()
            ]

        hostels = Hostel.objects.filter(is_active=True).order_by("name")

        return render(
            request,
            "hostel/admin_fees.html",
            {
                "records": records,
                "summary": summary,
                "hostels": hostels,
                "selected_hostel": hostel_id,
                "selected_status": status_filter,
                "search_query": search_query,
            },
        )


class AdminCreateHostelFeeView(LoginRequiredMixin, UserPassesTestMixin, View):
    def test_func(self):
        return _is_hostel_admin(self.request.user)

    def get(self, request):
        initial_data = {}
        student_id = request.GET.get("student_id")
        if student_id:
            student = Student.objects.filter(pk=student_id).first()
            if student:
                initial_data["student"] = student

        form = HostelFeeDemandForm(initial=initial_data)
        return render(request, "hostel/admin_fee_form.html", {"form": form})

    def post(self, request):
        form = HostelFeeDemandForm(request.POST)
        if form.is_valid():
            fee_subtype = form.cleaned_data["fee_subtype"]
            student = form.cleaned_data["student"]
            record = FeeRecord.objects.create(
                student=student,
                fee_type="HOSTEL",
                title=f"Hostel - {fee_subtype}",
                academic_year=form.cleaned_data["academic_year"],
                amount=form.cleaned_data["amount"],
                due_date=form.cleaned_data.get("due_date"),
                remarks=form.cleaned_data.get("remarks") or "",
                status="PENDING",
            )
            messages.success(
                request,
                f"Successfully issued '{record.title}' of ₹{record.amount:,.2f} for {student.name}!",
            )
            return redirect("hostel:admin_fees")

        return render(request, "hostel/admin_fee_form.html", {"form": form})


class AdminRecordHostelPaymentView(LoginRequiredMixin, UserPassesTestMixin, View):
    def test_func(self):
        return _is_hostel_admin(self.request.user)

    def get(self, request, fee_id):
        record = get_object_or_404(
            FeeRecord.objects.select_related("student"),
            pk=fee_id,
            fee_type="HOSTEL",
        )
        if record.balance_amount <= 0:
            messages.info(request, f"Fee record '{record.title}' is already fully paid.")
            return redirect("hostel:admin_fees")

        form = HostelFeePaymentForm(
            initial={
                "amount": record.balance_amount,
                "payment_date": timezone.now().date(),
                "payment_mode": "CASH",
            }
        )
        return render(request, "hostel/admin_fee_payment_form.html", {"form": form, "record": record})

    def post(self, request, fee_id):
        record = get_object_or_404(
            FeeRecord.objects.select_related("student"),
            pk=fee_id,
            fee_type="HOSTEL",
        )
        form = HostelFeePaymentForm(request.POST)
        if form.is_valid():
            payment = form.save(commit=False)
            payment.fee_record = record
            if not payment.receipt_number:
                payment.receipt_number = f"REC-HST-{timezone.now().strftime('%y%m%d')}-{uuid.uuid4().hex[:6].upper()}"
            try:
                payment.save()
                messages.success(
                    request,
                    f"Payment of ₹{payment.amount:,.2f} recorded! Receipt: {payment.receipt_number}",
                )
                return redirect("hostel:admin_fees")
            except Exception as e:
                messages.error(request, f"Failed to record payment: {e}")
        return render(request, "hostel/admin_fee_payment_form.html", {"form": form, "record": record})


class StudentHostelFeeView(LoginRequiredMixin, View):
    def get(self, request):
        student = Student.objects.filter(user=request.user).first()
        if not student:
            if _is_hostel_admin(request.user):
                return redirect("hostel:admin_fees")
            messages.warning(request, "Student profile required to view hostel fees.")
            return redirect("home")

        fee_data = get_student_hostel_fees(student)
        return render(
            request,
            "hostel/student_fees.html",
            {
                "student": student,
                "fee_data": fee_data,
            },
        )


class AdminHostelAttendanceView(LoginRequiredMixin, UserPassesTestMixin, View):
    def test_func(self):
        return _is_hostel_admin(self.request.user)

    def _get_target_date(self, request):
        date_str = request.GET.get("date") or request.POST.get("date")
        if date_str:
            try:
                from datetime import datetime
                return datetime.strptime(date_str, "%Y-%m-%d").date()
            except ValueError:
                pass
        return timezone.now().date()

    def _get_hostel(self, request):
        hostel_id = request.GET.get("hostel") or request.POST.get("hostel")
        if hostel_id:
            return Hostel.objects.filter(pk=hostel_id, is_active=True).first()
        assigned_ids = get_user_assigned_hostel_ids(request.user)
        if not request.user.is_superuser:
            return Hostel.objects.filter(id__in=assigned_ids, is_active=True).first()
        return Hostel.objects.filter(is_active=True).first()

    def get(self, request):
        if not request.user.is_superuser:
            assigned_ids = get_user_assigned_hostel_ids(request.user)
            hostels = Hostel.objects.filter(id__in=assigned_ids, is_active=True).order_by("name")
        else:
            hostels = Hostel.objects.filter(is_active=True).order_by("name")

        selected_hostel = self._get_hostel(request)
        if selected_hostel and not is_warden_for_hostel(request.user, selected_hostel):
            raise PermissionDenied("You are not authorized to access attendance for this hostel.")

        target_date = self._get_target_date(request)

        block_id = request.GET.get("block")
        room_id = request.GET.get("room")

        blocks = HostelBlock.objects.filter(hostel=selected_hostel, is_active=True) if selected_hostel else []
        rooms = HostelRoom.objects.filter(hostel=selected_hostel, is_active=True) if selected_hostel else []

        roster = []
        present_count = 0
        absent_count = 0
        permission_count = 0
        leave_count = 0
        marked_count = 0

        if selected_hostel:
            alloc_qs = HostelAllocation.objects.filter(
                hostel=selected_hostel,
                status="ACTIVE",
            ).select_related("student", "room", "bed", "block", "floor")

            if block_id:
                alloc_qs = alloc_qs.filter(block_id=block_id)
            if room_id:
                alloc_qs = alloc_qs.filter(room_id=room_id)

            allocations = list(alloc_qs.order_by("room__room_number", "bed__bed_number", "student__name"))

            existing_map = {
                att.student_id: att
                for att in HostelAttendance.objects.filter(hostel=selected_hostel, date=target_date)
            }

            for alloc in allocations:
                att = existing_map.get(alloc.student_id)
                current_status = att.status if att else "PRESENT"
                remarks = att.remarks if att else ""

                if att:
                    marked_count += 1
                    if att.status == "PRESENT":
                        present_count += 1
                    elif att.status == "ABSENT":
                        absent_count += 1
                    elif att.status == "PERMISSION":
                        permission_count += 1
                    elif att.status == "LEAVE":
                        leave_count += 1

                roster.append({
                    "allocation": alloc,
                    "student": alloc.student,
                    "room": alloc.room,
                    "bed": alloc.bed,
                    "status": current_status,
                    "remarks": remarks,
                    "is_marked": att is not None,
                })

        total_residents = len(roster)
        att_pct = round((present_count / marked_count * 100), 1) if marked_count > 0 else 0.0

        return render(
            request,
            "hostel/admin_attendance.html",
            {
                "hostels": hostels,
                "selected_hostel": selected_hostel,
                "target_date": target_date,
                "blocks": blocks,
                "rooms": rooms,
                "selected_block": block_id,
                "selected_room": room_id,
                "roster": roster,
                "total_residents": total_residents,
                "marked_count": marked_count,
                "present_count": present_count,
                "absent_count": absent_count,
                "permission_count": permission_count,
                "leave_count": leave_count,
                "attendance_percentage": att_pct,
            },
        )

    def post(self, request):
        selected_hostel = self._get_hostel(request)
        target_date = self._get_target_date(request)

        if not selected_hostel or not is_warden_for_hostel(request.user, selected_hostel):
            raise PermissionDenied("You are not authorized to mark attendance for this hostel.")

        alloc_qs = HostelAllocation.objects.filter(
            hostel=selected_hostel,
            status="ACTIVE",
        ).select_related("student", "room")

        block_id = request.POST.get("block")
        room_id = request.POST.get("room")
        if block_id:
            alloc_qs = alloc_qs.filter(block_id=block_id)
        if room_id:
            alloc_qs = alloc_qs.filter(room_id=room_id)

        allocations = list(alloc_qs)
        saved_count = 0

        with transaction.atomic():
            for alloc in allocations:
                key_status = f"status_{alloc.student_id}"
                key_remarks = f"remarks_{alloc.student_id}"

                status_val = request.POST.get(key_status, "PRESENT")
                remarks_val = request.POST.get(key_remarks, "").strip()

                HostelAttendance.objects.update_or_create(
                    student=alloc.student,
                    date=target_date,
                    defaults={
                        "hostel": alloc.hostel,
                        "room": alloc.room,
                        "status": status_val,
                        "remarks": remarks_val,
                        "marked_by": request.user,
                    },
                )
                saved_count += 1

        messages.success(
            request,
            f"Successfully recorded attendance for {saved_count} residents in {selected_hostel.name} on {target_date.strftime('%d %b %Y')}!",
        )
        return redirect(f"{request.path}?hostel={selected_hostel.id}&date={target_date.isoformat()}")


class StudentHostelAttendanceView(LoginRequiredMixin, View):
    def get(self, request):
        student = Student.objects.filter(user=request.user).first()
        if not student:
            if _is_hostel_admin(request.user):
                return redirect("hostel:admin_attendance")
            messages.warning(request, "Student profile required to view hostel attendance.")
            return redirect("home")

        attendances = list(
            HostelAttendance.objects.filter(student=student)
            .select_related("hostel", "room")
            .order_by("-date")
        )

        total_days = len(attendances)
        present_count = sum(1 for a in attendances if a.status == "PRESENT")
        absent_count = sum(1 for a in attendances if a.status == "ABSENT")
        permission_count = sum(1 for a in attendances if a.status == "PERMISSION")
        leave_count = sum(1 for a in attendances if a.status == "LEAVE")
        att_pct = round((present_count / total_days * 100), 1) if total_days > 0 else 0.0

        return render(
            request,
            "hostel/student_attendance.html",
            {
                "student": student,
                "attendances": attendances,
                "total_days": total_days,
                "present_count": present_count,
                "absent_count": absent_count,
                "permission_count": permission_count,
                "leave_count": leave_count,
                "attendance_percentage": att_pct,
            },
        )


class StudentComplaintListView(LoginRequiredMixin, View):
    def get(self, request):
        student = Student.objects.filter(user=request.user).first()
        if not student:
            if _is_hostel_admin(request.user):
                return redirect("hostel:admin_complaints")
            messages.warning(request, "Student profile required to view complaints.")
            return redirect("home")

        complaints = list(
            HostelComplaint.objects.filter(student=student)
            .select_related("hostel", "room", "assigned_staff")
            .order_by("-created_at")
        )
        open_count = sum(1 for c in complaints if c.status in ["OPEN", "ASSIGNED", "IN_PROGRESS"])
        resolved_count = sum(1 for c in complaints if c.status in ["RESOLVED", "CLOSED"])

        return render(
            request,
            "hostel/student_complaint_list.html",
            {
                "student": student,
                "complaints": complaints,
                "open_count": open_count,
                "resolved_count": resolved_count,
            },
        )


class StudentComplaintCreateView(LoginRequiredMixin, View):
    def get(self, request):
        student = Student.objects.filter(user=request.user).first()
        if not student:
            messages.error(request, "Only registered students can submit maintenance complaints.")
            return redirect("home")

        allocation = (
            HostelAllocation.objects.filter(student=student, status="ACTIVE")
            .select_related("hostel", "room")
            .first()
        )
        form = StudentComplaintForm()
        return render(
            request,
            "hostel/student_complaint_form.html",
            {
                "student": student,
                "allocation": allocation,
                "form": form,
            },
        )

    def post(self, request):
        student = Student.objects.filter(user=request.user).first()
        if not student:
            messages.error(request, "Only registered students can submit complaints.")
            return redirect("home")

        allocation = (
            HostelAllocation.objects.filter(student=student, status="ACTIVE")
            .select_related("hostel", "room")
            .first()
        )
        form = StudentComplaintForm(request.POST, request.FILES)
        if form.is_valid():
            complaint = form.save(commit=False)
            complaint.student = student
            if allocation:
                complaint.hostel = allocation.hostel
                complaint.room = allocation.room
            else:
                first_hostel = Hostel.objects.filter(is_active=True).first()
                if not first_hostel:
                    messages.error(request, "No active hostels available to route complaint.")
                    return redirect("hostel:student_complaint_list")
                complaint.hostel = first_hostel

            complaint.save()
            messages.success(
                request,
                f"Complaint '{complaint.title}' registered successfully! Tracking ID: {complaint.complaint_id}",
            )
            return redirect("hostel:student_complaint_detail", pk=complaint.pk)

        return render(
            request,
            "hostel/student_complaint_form.html",
            {
                "student": student,
                "allocation": allocation,
                "form": form,
            },
        )


class StudentComplaintDetailView(LoginRequiredMixin, View):
    def get(self, request, pk):
        complaint = get_object_or_404(
            HostelComplaint.objects.select_related(
                "hostel", "room", "student", "assigned_staff", "resolved_by"
            ),
            pk=pk,
        )
        student = Student.objects.filter(user=request.user).first()
        is_owner = bool(student and complaint.student_id == student.id)
        is_warden = is_warden_for_hostel(request.user, complaint.hostel)
        can_access = request.user.is_superuser or is_warden or is_owner

        if not can_access:
            raise PermissionDenied("You do not have permission to view this complaint.")

        return render(
            request,
            "hostel/student_complaint_detail.html",
            {
                "complaint": complaint,
                "is_admin": (request.user.is_superuser or is_warden),
            },
        )


class AdminComplaintListView(LoginRequiredMixin, UserPassesTestMixin, View):
    def test_func(self):
        return _is_hostel_admin(self.request.user)

    def get(self, request):
        qs = HostelComplaint.objects.select_related(
            "student", "hostel", "room", "assigned_staff"
        ).order_by("-created_at")

        hostel_id = request.GET.get("hostel")
        status_filter = request.GET.get("status")
        category_filter = request.GET.get("category")
        priority_filter = request.GET.get("priority")
        search_query = request.GET.get("search", "").strip()

        if not request.user.is_superuser:
            assigned_ids = get_user_assigned_hostel_ids(request.user)
            qs = qs.filter(hostel_id__in=assigned_ids)

        if hostel_id:
            qs = qs.filter(hostel_id=hostel_id)
        if status_filter:
            qs = qs.filter(status=status_filter)
        if category_filter:
            qs = qs.filter(category=category_filter)
        if priority_filter:
            qs = qs.filter(priority=priority_filter)
        if search_query:
            qs = qs.filter(
                Q(complaint_id__icontains=search_query)
                | Q(title__icontains=search_query)
                | Q(student__name__icontains=search_query)
                | Q(student__roll_no__icontains=search_query)
            )

        complaints = list(qs)
        if not request.user.is_superuser:
            assigned_ids = get_user_assigned_hostel_ids(request.user)
            hostels = Hostel.objects.filter(id__in=assigned_ids, is_active=True).order_by("name")
        else:
            hostels = Hostel.objects.filter(is_active=True).order_by("name")

        open_count = sum(1 for c in complaints if c.status == "OPEN")
        assigned_count = sum(1 for c in complaints if c.status in ["ASSIGNED", "IN_PROGRESS"])
        resolved_count = sum(1 for c in complaints if c.status in ["RESOLVED", "CLOSED"])

        return render(
            request,
            "hostel/admin_complaint_list.html",
            {
                "complaints": complaints,
                "hostels": hostels,
                "selected_hostel": hostel_id,
                "selected_status": status_filter,
                "selected_category": category_filter,
                "selected_priority": priority_filter,
                "search_query": search_query,
                "open_count": open_count,
                "assigned_count": assigned_count,
                "resolved_count": resolved_count,
                "category_choices": HostelComplaint.CATEGORY_CHOICES,
                "priority_choices": HostelComplaint.PRIORITY_CHOICES,
                "status_choices": HostelComplaint.STATUS_CHOICES,
            },
        )


class AdminComplaintDetailView(LoginRequiredMixin, UserPassesTestMixin, View):
    def test_func(self):
        return _is_hostel_admin(self.request.user)

    def get(self, request, pk):
        complaint = get_object_or_404(
            HostelComplaint.objects.select_related(
                "student", "hostel", "room", "assigned_staff", "resolved_by"
            ),
            pk=pk,
        )
        if not is_warden_for_hostel(request.user, complaint.hostel):
            raise PermissionDenied("You are not authorized to manage complaints for this hostel.")

        form = AdminComplaintUpdateForm(instance=complaint)
        return render(
            request,
            "hostel/admin_complaint_detail.html",
            {
                "complaint": complaint,
                "form": form,
            },
        )

    def post(self, request, pk):
        complaint = get_object_or_404(
            HostelComplaint.objects.select_related(
                "student", "hostel", "room", "assigned_staff", "resolved_by"
            ),
            pk=pk,
        )
        if not is_warden_for_hostel(request.user, complaint.hostel):
            raise PermissionDenied("You are not authorized to manage complaints for this hostel.")
        form = AdminComplaintUpdateForm(request.POST, instance=complaint)
        if form.is_valid():
            comp = form.save(commit=False)
            if comp.status in ["RESOLVED", "CLOSED"]:
                comp.resolved_by = request.user
                comp.resolved_date = timezone.now()
            comp.save()

            if comp.student and comp.student.user:
                if comp.status == "RESOLVED":
                    Notification.objects.create(
                        recipient=comp.student.user,
                        title="Hostel Complaint Resolved",
                        message=f"Your complaint '{comp.title}' ({comp.complaint_id}) has been marked as resolved: {comp.resolution or 'Resolution confirmed by staff'}.",
                        link=f"/hostel/complaints/{comp.pk}/",
                    )
                else:
                    Notification.objects.create(
                        recipient=comp.student.user,
                        title="Hostel Complaint Updated",
                        message=f"Your complaint '{comp.title}' ({comp.complaint_id}) status was updated to '{comp.get_status_display()}'.",
                        link=f"/hostel/complaints/{comp.pk}/",
                    )

            messages.success(
                request,
                f"Complaint {comp.complaint_id} updated successfully (Status: {comp.get_status_display()})!",
            )
            return redirect("hostel:admin_complaint_detail", pk=comp.pk)

        return render(
            request,
            "hostel/admin_complaint_detail.html",
            {
                "complaint": complaint,
                "form": form,
            },
        )


class AdminHostelNoticeListView(LoginRequiredMixin, UserPassesTestMixin, View):
    def test_func(self):
        return _is_hostel_admin(self.request.user)

    def get(self, request):
        qs = HostelNotice.objects.select_related("hostel", "created_by").order_by("-publish_date", "-created_at")
        if not request.user.is_superuser:
            assigned_ids = get_user_assigned_hostel_ids(request.user)
            qs = qs.filter(hostel_id__in=assigned_ids)
            hostels = Hostel.objects.filter(id__in=assigned_ids, is_active=True).order_by("name")
        else:
            hostels = Hostel.objects.filter(is_active=True).order_by("name")

        hostel_id = request.GET.get("hostel")
        if hostel_id:
            qs = qs.filter(hostel_id=hostel_id)

        notices = list(qs)
        return render(
            request,
            "hostel/admin_notice_list.html",
            {
                "notices": notices,
                "hostels": hostels,
                "selected_hostel": hostel_id,
            },
        )


class AdminCreateHostelNoticeView(LoginRequiredMixin, UserPassesTestMixin, View):
    def test_func(self):
        return _is_hostel_admin(self.request.user)

    def get(self, request):
        form = HostelNoticeForm(user=request.user)
        return render(request, "hostel/admin_notice_form.html", {"form": form})

    def post(self, request):
        form = HostelNoticeForm(request.POST, request.FILES, user=request.user)
        if form.is_valid():
            notice = form.save(commit=False)
            if not is_warden_for_hostel(request.user, notice.hostel):
                raise PermissionDenied("You can only publish notices for your assigned hostel.")
            notice.created_by = request.user
            notice.save()

            # Integrate existing Notification architecture
            active_student_user_ids = list(
                HostelAllocation.objects.filter(
                    hostel=notice.hostel,
                    status="ACTIVE",
                    student__user__isnull=False,
                ).values_list("student__user_id", flat=True)
            )

            Notification.objects.bulk_create([
                Notification(
                    recipient_id=uid,
                    title=f"Hostel Notice: {notice.title}",
                    message=notice.message[:250],
                    link="/hostel/notices/",
                )
                for uid in active_student_user_ids
            ])

            messages.success(
                request,
                f"Hostel notice '{notice.title}' published successfully for {notice.hostel.name} ({len(active_student_user_ids)} residents notified)!",
            )
            return redirect("hostel:admin_notices")

        return render(request, "hostel/admin_notice_form.html", {"form": form})


class StudentHostelNoticeListView(LoginRequiredMixin, View):
    def get(self, request):
        student = Student.objects.filter(user=request.user).first()
        allocation = None
        if student:
            allocation = (
                HostelAllocation.objects.filter(student=student, status="ACTIVE")
                .select_related("hostel", "room")
                .first()
            )

        if allocation:
            notices = list(
                HostelNotice.objects.filter(hostel=allocation.hostel, is_active=True).order_by(
                    "-publish_date", "-created_at"
                )
            )
        else:
            notices = list(
                HostelNotice.objects.filter(is_active=True).order_by("-publish_date", "-created_at")[:15]
            )

        return render(
            request,
            "hostel/student_notices.html",
            {
                "student": student,
                "allocation": allocation,
                "notices": notices,
            },
        )


class StudentVisitorListView(LoginRequiredMixin, View):
    def get(self, request):
        student = Student.objects.filter(user=request.user).first()
        if not student:
            messages.warning(request, "Student profile required to view visitor logs.")
            return redirect("home")

        allocation = (
            HostelAllocation.objects.filter(student=student, status="ACTIVE")
            .select_related("hostel", "room", "bed")
            .first()
        )

        visitors = (
            HostelVisitor.objects.filter(student=student)
            .select_related("hostel", "approved_by")
            .order_by("-visit_date", "-created_at")
        )

        pending_count = sum(1 for v in visitors if v.status == "PENDING")
        approved_count = sum(1 for v in visitors if v.status == "APPROVED")
        checked_in_count = sum(1 for v in visitors if v.status == "CHECKED_IN")

        return render(
            request,
            "hostel/student_visitors.html",
            {
                "student": student,
                "allocation": allocation,
                "visitors": visitors,
                "pending_count": pending_count,
                "approved_count": approved_count,
                "checked_in_count": checked_in_count,
            },
        )


class StudentVisitorCreateView(LoginRequiredMixin, View):
    def get(self, request):
        student = Student.objects.filter(user=request.user).first()
        if not student:
            messages.warning(request, "Student profile required.")
            return redirect("home")

        allocation = HostelAllocation.objects.filter(student=student, status="ACTIVE").select_related("hostel").first()
        if not allocation:
            messages.error(request, "You must have an active hostel allocation to request a visitor pass.")
            return redirect("hostel:student_visitors")

        form = StudentVisitorRequestForm()
        return render(
            request,
            "hostel/student_visitor_form.html",
            {"form": form, "student": student, "allocation": allocation},
        )

    def post(self, request):
        student = Student.objects.filter(user=request.user).first()
        if not student:
            messages.warning(request, "Student profile required.")
            return redirect("home")

        allocation = HostelAllocation.objects.filter(student=student, status="ACTIVE").select_related("hostel").first()
        if not allocation:
            messages.error(request, "You must have an active hostel allocation to request a visitor pass.")
            return redirect("hostel:student_visitors")

        form = StudentVisitorRequestForm(request.POST)
        if form.is_valid():
            visitor = form.save(commit=False)
            visitor.student = student
            visitor.hostel = allocation.hostel
            visitor.status = "PENDING"
            visitor.save()
            messages.success(
                request,
                f"Visitor pass request for {visitor.visitor_name} submitted successfully! Awaiting warden approval.",
            )
            return redirect("hostel:student_visitors")

        return render(
            request,
            "hostel/student_visitor_form.html",
            {"form": form, "student": student, "allocation": allocation},
        )


class AdminVisitorListView(LoginRequiredMixin, View):
    def get(self, request):
        if not _is_hostel_admin(request.user):
            raise PermissionDenied("Hostel management access required.")

        assigned_hostel_ids = get_user_assigned_hostel_ids(request.user)
        accessible_hostels = Hostel.objects.filter(id__in=assigned_hostel_ids, is_active=True)

        queryset = (
            HostelVisitor.objects.filter(hostel_id__in=assigned_hostel_ids)
            .select_related("student", "student__user", "hostel", "approved_by")
        )

        hostel_id = request.GET.get("hostel", "").strip()
        status = request.GET.get("status", "").strip()
        search = request.GET.get("search", "").strip()
        date = request.GET.get("date", "").strip()

        if hostel_id and hostel_id.isdigit():
            queryset = queryset.filter(hostel_id=int(hostel_id))
        if status:
            queryset = queryset.filter(status=status)
        if date:
            queryset = queryset.filter(visit_date=date)
        if search:
            queryset = queryset.filter(
                Q(visitor_name__icontains=search)
                | Q(phone__icontains=search)
                | Q(purpose__icontains=search)
                | Q(student__name__icontains=search)
                | Q(student__roll_no__icontains=search)
            )

        queryset = queryset.order_by("-visit_date", "-created_at")

        all_assigned = HostelVisitor.objects.filter(hostel_id__in=assigned_hostel_ids)
        visitor_stats = all_assigned.aggregate(
            total=Count("id"),
            pending=Count("id", filter=Q(status="PENDING")),
            approved=Count("id", filter=Q(status="APPROVED")),
            checked_in=Count("id", filter=Q(status="CHECKED_IN")),
            checked_out=Count("id", filter=Q(status="CHECKED_OUT")),
        )
        total_count = visitor_stats["total"]
        pending_count = visitor_stats["pending"]
        approved_count = visitor_stats["approved"]
        checked_in_count = visitor_stats["checked_in"]
        checked_out_count = visitor_stats["checked_out"]

        paginator = Paginator(queryset, 20)
        page_number = request.GET.get("page")
        page_obj = paginator.get_page(page_number)

        return render(
            request,
            "hostel/admin_visitors.html",
            {
                "visitors": page_obj,
                "page_obj": page_obj,
                "hostels": accessible_hostels,
                "selected_hostel": hostel_id,
                "selected_status": status,
                "selected_date": date,
                "search_query": search,
                "status_choices": HostelVisitor.STATUS_CHOICES,
                "total_count": total_count,
                "pending_count": pending_count,
                "approved_count": approved_count,
                "checked_in_count": checked_in_count,
                "checked_out_count": checked_out_count,
            },
        )


class AdminVisitorUpdateView(LoginRequiredMixin, View):
    def get(self, request, pk):
        if not _is_hostel_admin(request.user):
            raise PermissionDenied("Hostel management access required.")
        visitor = get_object_or_404(
            HostelVisitor.objects.select_related("student", "hostel", "approved_by"),
            pk=pk,
        )
        if not is_warden_for_hostel(request.user, visitor.hostel):
            raise PermissionDenied("You can only manage visitor passes for your assigned hostel.")

        form = AdminVisitorUpdateForm(instance=visitor)
        return render(
            request,
            "hostel/admin_visitor_form.html",
            {"form": form, "visitor": visitor},
        )

    def post(self, request, pk):
        if not _is_hostel_admin(request.user):
            raise PermissionDenied("Hostel management access required.")
        visitor = get_object_or_404(
            HostelVisitor.objects.select_related("student", "hostel", "approved_by"),
            pk=pk,
        )
        if not is_warden_for_hostel(request.user, visitor.hostel):
            raise PermissionDenied("You can only manage visitor passes for your assigned hostel.")

        form = AdminVisitorUpdateForm(request.POST, instance=visitor)
        if form.is_valid():
            v = form.save(commit=False)
            if v.status in ("APPROVED", "CHECKED_IN", "CHECKED_OUT", "REJECTED") and not v.approved_by:
                v.approved_by = request.user
            v.save()

            if visitor.student and visitor.student.user:
                status_display = dict(HostelVisitor.STATUS_CHOICES).get(v.status, v.status)
                Notification.objects.create(
                    recipient=visitor.student.user,
                    title=f"Visitor Pass Update: {v.visitor_name}",
                    message=f"Visitor pass for {v.visitor_name} status updated to '{status_display}'.",
                    link="/hostel/visitors/",
                )

            messages.success(request, f"Visitor record for {v.visitor_name} updated successfully.")
            return redirect("hostel:admin_visitors")

        return render(
            request,
            "hostel/admin_visitor_form.html",
            {"form": form, "visitor": visitor},
        )
