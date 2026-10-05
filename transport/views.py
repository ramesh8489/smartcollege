import io
from decimal import Decimal
from django.shortcuts import render, redirect, get_object_or_404
from django.views import View
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.utils import timezone
from django.db import transaction
from django.db.models import Q, Count
from django.core.paginator import Paginator
from django.http import HttpResponse

from students.models import Student
from fees.models import FeeRecord, FeePayment
from timetable.models import Notification
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
from .forms import (
    VehicleForm,
    RouteForm,
    StopForm,
    DriverForm,
    ConductorForm,
    TransportApplicationForm,
    ApplicationReviewForm,
    TransportAllocationForm,
    TransportPassForm,
    TransportAttendanceForm,
    VehicleMaintenanceForm,
    TransportComplaintForm,
    AdminComplaintUpdateForm,
    TransportIncidentForm,
    TransportFeeDemandForm,
    TransportFeePaymentForm,
)
from .services import (
    get_student_transport_summary,
    get_student_transport_fees,
    get_admin_transport_fees_summary,
    get_transport_admin_dashboard_metrics,
    notify_transport_event,
)


def _is_transport_admin(user):
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser or user.is_staff:
        return True
    return hasattr(user, "transport_staff_profile") and user.transport_staff_profile.is_active


# ================================================================
# PORTAL / DASHBOARD ENTRY ROUTING
# ================================================================
class TransportHomeView(LoginRequiredMixin, View):
    def get(self, request):
        if _is_transport_admin(request.user):
            return redirect("transport:admin_dashboard")
        student = Student.objects.filter(user=request.user).first()
        if not student:
            messages.warning(request, "Student profile required to access the transport portal.")
            return redirect("home")
        return redirect("transport:student_portal")


# ================================================================
# STUDENT PORTAL VIEWS
# ================================================================
class StudentTransportPortalView(LoginRequiredMixin, View):
    def get(self, request):
        student = Student.objects.filter(user=request.user).first()
        if not student:
            messages.error(request, "No student profile linked to your user account.")
            return redirect("home")
        data = get_student_transport_summary(student)
        return render(
            request,
            "transport/student_portal.html",
            {
                "student": student,
                "data": data,
                "allocation": data["allocation"],
                "pass": data["pass"],
                "fees": data["fees"],
                "attendance": data["attendance"],
                "complaints": data["complaints"],
                "applications": data["applications"],
            },
        )


class StudentTransportApplicationCreateView(LoginRequiredMixin, View):
    def get(self, request):
        student = get_object_or_404(Student, user=request.user)
        # Check active application
        existing_active = TransportApplication.objects.filter(student=student, status="PENDING").first()
        if existing_active:
            messages.info(request, f"You already have a pending transport application: {existing_active.application_id}")
            return redirect("transport:application_detail", pk=existing_active.pk)

        existing_alloc = TransportAllocation.objects.filter(student=student, status="ACTIVE").first()
        if existing_alloc:
            messages.info(request, f"You already have an active bus allocation: {existing_alloc.allocation_id}")
            return redirect("transport:student_portal")

        form = TransportApplicationForm(initial={
            "parent_name": student.parent_name,
            "parent_phone": student.parent_phone,
            "student_phone": student.phone,
        })
        return render(request, "transport/application_form.html", {"form": form, "student": student})

    def post(self, request):
        student = get_object_or_404(Student, user=request.user)
        existing_active = TransportApplication.objects.filter(student=student, status="PENDING").first()
        if existing_active:
            messages.warning(request, f"You already have a pending transport application: {existing_active.application_id}")
            return redirect("transport:application_detail", pk=existing_active.pk)

        existing_alloc = TransportAllocation.objects.filter(student=student, status="ACTIVE").first()
        if existing_alloc:
            messages.warning(request, f"You already have an active bus allocation: {existing_alloc.allocation_id}")
            return redirect("transport:student_portal")

        form = TransportApplicationForm(request.POST)
        if form.is_valid():
            app = form.save(commit=False)
            app.student = student
            app.status = "PENDING"
            app.save()

            notify_transport_event(
                request.user,
                title="Transport Application Submitted",
                message=f"Your transport request {app.application_id} for Route {app.route.code} has been received.",
                link=f"/transport/applications/{app.pk}/",
            )
            messages.success(request, f"Application {app.application_id} submitted successfully! Our transport office will review it.")
            return redirect("transport:application_detail", pk=app.pk)

        return render(request, "transport/application_form.html", {"form": form, "student": student})


class StudentTransportApplicationListView(LoginRequiredMixin, View):
    def get(self, request):
        student = get_object_or_404(Student, user=request.user)
        applications = TransportApplication.objects.filter(student=student).select_related("route", "stop").order_by("-application_date")
        return render(request, "transport/application_list.html", {"applications": applications, "student": student})


class StudentTransportApplicationDetailView(LoginRequiredMixin, View):
    def get(self, request, pk):
        is_admin = _is_transport_admin(request.user)
        if is_admin:
            app = get_object_or_404(TransportApplication.objects.select_related("student", "route", "stop"), pk=pk)
            review_form = ApplicationReviewForm()
            return render(request, "transport/application_detail.html", {"application": app, "is_admin": True, "review_form": review_form})
        else:
            student = get_object_or_404(Student, user=request.user)
            app = get_object_or_404(TransportApplication.objects.select_related("student", "route", "stop"), pk=pk)
            if app.student_id != student.id:
                raise PermissionDenied("You can only view your own transport applications.")
            return render(request, "transport/application_detail.html", {"application": app, "is_admin": False})


class StudentTransportPassView(LoginRequiredMixin, View):
    def get(self, request):
        student = get_object_or_404(Student, user=request.user)
        pass_obj = TransportPass.objects.filter(student=student, status="ACTIVE").select_related("allocation", "allocation__vehicle", "allocation__route", "allocation__stop").first()
        if not pass_obj:
            pass_obj = TransportPass.objects.filter(student=student).select_related("allocation", "allocation__vehicle", "allocation__route", "allocation__stop").order_by("-issue_date").first()
        return render(request, "transport/student_pass.html", {"pass": pass_obj, "student": student})


class StudentTransportPassPdfView(LoginRequiredMixin, View):
    def get(self, request):
        student = get_object_or_404(Student, user=request.user)
        pass_obj = TransportPass.objects.filter(student=student, status="ACTIVE").select_related("allocation", "allocation__vehicle", "allocation__route", "allocation__stop").first()
        if not pass_obj:
            messages.error(request, "No active transport pass found to download.")
            return redirect("transport:student_portal")
        return generate_single_pass_pdf(pass_obj)


def generate_single_pass_pdf(pass_obj):
    """Generates an institutional PDF bus pass card."""
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.enums import TA_CENTER, TA_LEFT

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=36,
        rightMargin=36,
        topMargin=36,
        bottomMargin=36,
    )
    styles = getSampleStyleSheet()

    header_style = ParagraphStyle(
        "PassHeader",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=13,
        leading=16,
        textColor=colors.HexColor("#0F172A"),
        alignment=TA_CENTER,
    )
    sub_style = ParagraphStyle(
        "PassSub",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9,
        leading=12,
        textColor=colors.HexColor("#475569"),
        alignment=TA_CENTER,
    )
    bold_cell = ParagraphStyle(
        "PassBoldCell",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=9,
        leading=12,
        textColor=colors.HexColor("#0F172A"),
    )
    reg_cell = ParagraphStyle(
        "PassRegCell",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9,
        leading=12,
        textColor=colors.HexColor("#334155"),
    )

    elements = []
    elements.append(Paragraph("SMART COLLEGE &middot; TAKSHASHILA UNIVERSITY", sub_style))
    elements.append(Paragraph("OFFICIAL STUDENT TRANSPORT PASS", header_style))
    elements.append(Paragraph(f"Academic Year {pass_obj.academic_year} &middot; Pass No: {pass_obj.pass_number}", sub_style))
    elements.append(Spacer(1, 16))

    alloc = pass_obj.allocation
    student = pass_obj.student

    card_rows = [
        [Paragraph("Student Name", bold_cell), Paragraph(student.name, reg_cell)],
        [Paragraph("Roll Number", bold_cell), Paragraph(student.roll_no, reg_cell)],
        [Paragraph("Course / Department", bold_cell), Paragraph(f"{student.course.name if student.course else '-'} ({student.department.name})", reg_cell)],
        [Paragraph("Bus / Vehicle Number", bold_cell), Paragraph(f"{alloc.vehicle.vehicle_number} ({alloc.vehicle.bus_name})", reg_cell)],
        [Paragraph("Route", bold_cell), Paragraph(f"{alloc.route.code} - {alloc.route.name}", reg_cell)],
        [Paragraph("Boarding Stop", bold_cell), Paragraph(alloc.stop.stop_name, reg_cell)],
        [Paragraph("Pickup Time / Drop Time", bold_cell), Paragraph(f"{alloc.stop.pickup_time.strftime('%I:%M %p')} &middot; {alloc.stop.drop_time.strftime('%I:%M %p')}", reg_cell)],
        [Paragraph("Seat Number", bold_cell), Paragraph(alloc.seat_number or "General / Open", reg_cell)],
        [Paragraph("Issue Date", bold_cell), Paragraph(str(pass_obj.issue_date), reg_cell)],
        [Paragraph("Expiry Date", bold_cell), Paragraph(str(pass_obj.expiry_date), reg_cell)],
        [Paragraph("Pass Status", bold_cell), Paragraph(pass_obj.get_status_display().upper(), bold_cell)],
    ]

    pass_table = Table(card_rows, colWidths=[150, 350])
    pass_table.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#F1F5F9")),
            ("BACKGROUND", (1, 0), (1, -1), colors.white),
            ("BOX", (0, 0), (-1, -1), 1.5, colors.HexColor("#1E293B")),
            ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ])
    )
    elements.append(pass_table)
    elements.append(Spacer(1, 20))
    elements.append(Paragraph("Notice: This pass is non-transferable and must be presented to the bus conductor or driver on boarding.", sub_style))

    doc.build(elements)
    buffer.seek(0)
    response = HttpResponse(buffer.getvalue(), content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="transport_pass_{student.roll_no}.pdf"'
    return response


class StudentTransportAttendanceView(LoginRequiredMixin, View):
    def get(self, request):
        student = get_object_or_404(Student, user=request.user)
        records = TransportAttendance.objects.filter(student=student).select_related("route", "vehicle", "boarding_stop").order_by("-date")
        total = records.count()
        present = records.filter(status="PRESENT").count()
        pct = round((present / total * 100), 1) if total > 0 else None
        return render(request, "transport/student_attendance.html", {"records": records, "student": student, "total": total, "present": present, "percentage": pct})


class StudentTransportFeesView(LoginRequiredMixin, View):
    def get(self, request):
        student = get_object_or_404(Student, user=request.user)
        fee_summary = get_student_transport_fees(student)
        return render(request, "transport/student_fees.html", {"student": student, "fees": fee_summary})


class StudentTransportComplaintListView(LoginRequiredMixin, View):
    def get(self, request):
        student = get_object_or_404(Student, user=request.user)
        complaints = TransportComplaint.objects.filter(student=student).select_related("route", "vehicle").order_by("-created_at")
        return render(request, "transport/student_complaint_list.html", {"complaints": complaints, "student": student})


class StudentTransportComplaintCreateView(LoginRequiredMixin, View):
    def get(self, request):
        student = get_object_or_404(Student, user=request.user)
        form = TransportComplaintForm()
        return render(request, "transport/student_complaint_form.html", {"form": form, "student": student})

    def post(self, request):
        student = get_object_or_404(Student, user=request.user)
        form = TransportComplaintForm(request.POST, request.FILES)
        if form.is_valid():
            comp = form.save(commit=False)
            comp.student = student
            comp.status = "OPEN"
            comp.save()

            notify_transport_event(
                request.user,
                title="Transport Complaint Registered",
                message=f"Complaint {comp.complaint_id} '{comp.title}' has been logged.",
                link=f"/transport/complaints/{comp.pk}/",
            )
            messages.success(request, f"Complaint {comp.complaint_id} submitted successfully!")
            return redirect("transport:student_complaint_detail", pk=comp.pk)

        return render(request, "transport/student_complaint_form.html", {"form": form, "student": student})


class StudentTransportComplaintDetailView(LoginRequiredMixin, View):
    def get(self, request, pk):
        is_admin = _is_transport_admin(request.user)
        if is_admin:
            comp = get_object_or_404(TransportComplaint.objects.select_related("student", "route", "vehicle", "assigned_staff"), pk=pk)
            update_form = AdminComplaintUpdateForm(instance=comp)
            return render(request, "transport/admin_complaint_detail.html", {"complaint": comp, "form": update_form})
        else:
            student = get_object_or_404(Student, user=request.user)
            comp = get_object_or_404(TransportComplaint.objects.select_related("student", "route", "vehicle", "assigned_staff"), pk=pk)
            if comp.student_id != student.id:
                raise PermissionDenied("You can only view your own complaints.")
            return render(request, "transport/student_complaint_detail.html", {"complaint": comp, "student": student})


# ================================================================
# ADMIN DASHBOARD & FLEET VIEWS
# ================================================================
class TransportAdminDashboardView(LoginRequiredMixin, View):
    def get(self, request):
        if not _is_transport_admin(request.user):
            raise PermissionDenied("Transport Administrative privilege required.")
        metrics = get_transport_admin_dashboard_metrics()
        return render(request, "transport/admin_dashboard.html", {"metrics": metrics})


# ----------------------------------------------------------------
# VEHICLE MANAGEMENT
# ----------------------------------------------------------------
class AdminVehicleListView(LoginRequiredMixin, View):
    def get(self, request):
        if not _is_transport_admin(request.user):
            raise PermissionDenied("Unauthorized.")
        qs = Vehicle.objects.all()
        q = request.GET.get("q", "").strip()
        status_filter = request.GET.get("status", "").strip()
        type_filter = request.GET.get("type", "").strip()

        if q:
            qs = qs.filter(Q(vehicle_number__icontains=q) | Q(registration_number__icontains=q) | Q(bus_name__icontains=q))
        if status_filter:
            qs = qs.filter(status=status_filter)
        if type_filter:
            qs = qs.filter(vehicle_type=type_filter)

        paginator = Paginator(qs.order_by("vehicle_number"), 15)
        page_obj = paginator.get_page(request.GET.get("page", 1))
        return render(request, "transport/admin_vehicle_list.html", {"page_obj": page_obj, "q": q, "status": status_filter, "type": type_filter})


class AdminVehicleCreateView(LoginRequiredMixin, View):
    def get(self, request):
        if not _is_transport_admin(request.user):
            raise PermissionDenied("Unauthorized.")
        form = VehicleForm()
        return render(request, "transport/admin_vehicle_form.html", {"form": form, "title": "Add New Bus / Vehicle"})

    def post(self, request):
        if not _is_transport_admin(request.user):
            raise PermissionDenied("Unauthorized.")
        form = VehicleForm(request.POST)
        if form.is_valid():
            vehicle = form.save()
            messages.success(request, f"Vehicle {vehicle.vehicle_number} registered successfully!")
            return redirect("transport:admin_vehicle_detail", pk=vehicle.pk)
        return render(request, "transport/admin_vehicle_form.html", {"form": form, "title": "Add New Bus / Vehicle"})


class AdminVehicleDetailView(LoginRequiredMixin, View):
    def get(self, request, pk):
        if not _is_transport_admin(request.user):
            raise PermissionDenied("Unauthorized.")
        vehicle = get_object_or_404(Vehicle, pk=pk)
        routes = vehicle.routes.filter(is_active=True).prefetch_related("stops")
        allocations = vehicle.allocations.filter(status="ACTIVE").select_related("student", "student__course", "route", "stop")
        maintenance = vehicle.maintenance_records.all().order_by("-service_date")[:10]
        return render(request, "transport/admin_vehicle_detail.html", {
            "vehicle": vehicle,
            "routes": routes,
            "allocations": allocations,
            "maintenance": maintenance,
        })


class AdminVehicleUpdateView(LoginRequiredMixin, View):
    def get(self, request, pk):
        if not _is_transport_admin(request.user):
            raise PermissionDenied("Unauthorized.")
        vehicle = get_object_or_404(Vehicle, pk=pk)
        form = VehicleForm(instance=vehicle)
        return render(request, "transport/admin_vehicle_form.html", {"form": form, "vehicle": vehicle, "title": f"Edit Vehicle {vehicle.vehicle_number}"})

    def post(self, request, pk):
        if not _is_transport_admin(request.user):
            raise PermissionDenied("Unauthorized.")
        vehicle = get_object_or_404(Vehicle, pk=pk)
        form = VehicleForm(request.POST, instance=vehicle)
        if form.is_valid():
            vehicle = form.save()
            messages.success(request, f"Vehicle {vehicle.vehicle_number} updated.")
            return redirect("transport:admin_vehicle_detail", pk=vehicle.pk)
        return render(request, "transport/admin_vehicle_form.html", {"form": form, "vehicle": vehicle, "title": f"Edit Vehicle {vehicle.vehicle_number}"})


# ----------------------------------------------------------------
# ROUTE & STOP MANAGEMENT
# ----------------------------------------------------------------
class AdminRouteListView(LoginRequiredMixin, View):
    def get(self, request):
        if not _is_transport_admin(request.user):
            raise PermissionDenied("Unauthorized.")
        qs = Route.objects.all().select_related("assigned_vehicle").prefetch_related("stops", "allocations")
        q = request.GET.get("q", "").strip()
        if q:
            qs = qs.filter(Q(code__icontains=q) | Q(name__icontains=q) | Q(start_point__icontains=q))
        paginator = Paginator(qs.order_by("code"), 15)
        page_obj = paginator.get_page(request.GET.get("page", 1))
        return render(request, "transport/admin_route_list.html", {"page_obj": page_obj, "q": q})


class AdminRouteCreateView(LoginRequiredMixin, View):
    def get(self, request):
        if not _is_transport_admin(request.user):
            raise PermissionDenied("Unauthorized.")
        form = RouteForm()
        return render(request, "transport/admin_route_form.html", {"form": form, "title": "Create Route"})

    def post(self, request):
        if not _is_transport_admin(request.user):
            raise PermissionDenied("Unauthorized.")
        form = RouteForm(request.POST)
        if form.is_valid():
            route = form.save()
            messages.success(request, f"Route {route.code} created successfully!")
            return redirect("transport:admin_route_detail", pk=route.pk)
        return render(request, "transport/admin_route_form.html", {"form": form, "title": "Create Route"})


class AdminRouteDetailView(LoginRequiredMixin, View):
    def get(self, request, pk):
        if not _is_transport_admin(request.user):
            raise PermissionDenied("Unauthorized.")
        route = get_object_or_404(Route.objects.select_related("assigned_vehicle"), pk=pk)
        stops = route.stops.all().order_by("stop_order")
        allocations = route.allocations.filter(status="ACTIVE").select_related("student", "stop", "vehicle")
        conductors = route.conductors.filter(is_active=True)
        driver = route.assigned_vehicle.driver if (route.assigned_vehicle and hasattr(route.assigned_vehicle, "driver")) else None
        return render(request, "transport/admin_route_detail.html", {
            "route": route,
            "stops": stops,
            "allocations": allocations,
            "conductors": conductors,
            "driver": driver,
        })


class AdminRouteUpdateView(LoginRequiredMixin, View):
    def get(self, request, pk):
        if not _is_transport_admin(request.user):
            raise PermissionDenied("Unauthorized.")
        route = get_object_or_404(Route, pk=pk)
        form = RouteForm(instance=route)
        return render(request, "transport/admin_route_form.html", {"form": form, "route": route, "title": f"Edit Route {route.code}"})

    def post(self, request, pk):
        if not _is_transport_admin(request.user):
            raise PermissionDenied("Unauthorized.")
        route = get_object_or_404(Route, pk=pk)
        form = RouteForm(request.POST, instance=route)
        if form.is_valid():
            route = form.save()
            messages.success(request, f"Route {route.code} updated.")
            return redirect("transport:admin_route_detail", pk=route.pk)
        return render(request, "transport/admin_route_form.html", {"form": form, "route": route, "title": f"Edit Route {route.code}"})


class AdminStopCreateView(LoginRequiredMixin, View):
    def get(self, request, route_id):
        if not _is_transport_admin(request.user):
            raise PermissionDenied("Unauthorized.")
        route = get_object_or_404(Route, pk=route_id)
        next_order = route.stops.count() + 1
        form = StopForm(initial={"stop_order": next_order})
        return render(request, "transport/admin_stop_form.html", {"form": form, "route": route, "title": f"Add Stop to {route.code}"})

    def post(self, request, route_id):
        if not _is_transport_admin(request.user):
            raise PermissionDenied("Unauthorized.")
        route = get_object_or_404(Route, pk=route_id)
        form = StopForm(request.POST)
        if form.is_valid():
            stop = form.save(commit=False)
            stop.route = route
            stop.save()
            messages.success(request, f"Stop '{stop.stop_name}' added to Route {route.code}.")
            return redirect("transport:admin_route_detail", pk=route.pk)
        return render(request, "transport/admin_stop_form.html", {"form": form, "route": route, "title": f"Add Stop to {route.code}"})


class AdminStopUpdateView(LoginRequiredMixin, View):
    def get(self, request, pk):
        if not _is_transport_admin(request.user):
            raise PermissionDenied("Unauthorized.")
        stop = get_object_or_404(Stop.objects.select_related("route"), pk=pk)
        form = StopForm(instance=stop)
        return render(request, "transport/admin_stop_form.html", {"form": form, "route": stop.route, "stop": stop, "title": f"Edit Stop {stop.stop_name}"})

    def post(self, request, pk):
        if not _is_transport_admin(request.user):
            raise PermissionDenied("Unauthorized.")
        stop = get_object_or_404(Stop.objects.select_related("route"), pk=pk)
        form = StopForm(request.POST, instance=stop)
        if form.is_valid():
            stop = form.save()
            messages.success(request, f"Stop '{stop.stop_name}' updated.")
            return redirect("transport:admin_route_detail", pk=stop.route_id)
        return render(request, "transport/admin_stop_form.html", {"form": form, "route": stop.route, "stop": stop, "title": f"Edit Stop {stop.stop_name}"})


class AdminStopDeleteView(LoginRequiredMixin, View):
    def post(self, request, pk):
        if not _is_transport_admin(request.user):
            raise PermissionDenied("Unauthorized.")
        stop = get_object_or_404(Stop, pk=pk)
        route_id = stop.route_id
        # Check active allocations
        if stop.allocations.filter(status="ACTIVE").exists():
            messages.error(request, f"Cannot delete stop '{stop.stop_name}' because active student allocations exist for it.")
            return redirect("transport:admin_route_detail", pk=route_id)
        stop.delete()
        messages.success(request, "Stop removed.")
        return redirect("transport:admin_route_detail", pk=route_id)


# ----------------------------------------------------------------
# DRIVER & CONDUCTOR VIEWS
# ----------------------------------------------------------------
class AdminDriverListView(LoginRequiredMixin, View):
    def get(self, request):
        if not _is_transport_admin(request.user):
            raise PermissionDenied("Unauthorized.")
        drivers = Driver.objects.all().select_related("assigned_vehicle").order_by("name")
        return render(request, "transport/admin_driver_list.html", {"drivers": drivers})


class AdminDriverCreateView(LoginRequiredMixin, View):
    def get(self, request):
        if not _is_transport_admin(request.user):
            raise PermissionDenied("Unauthorized.")
        form = DriverForm()
        return render(request, "transport/admin_driver_form.html", {"form": form, "title": "Register Driver"})

    def post(self, request):
        if not _is_transport_admin(request.user):
            raise PermissionDenied("Unauthorized.")
        form = DriverForm(request.POST)
        if form.is_valid():
            d = form.save()
            messages.success(request, f"Driver {d.name} registered.")
            return redirect("transport:admin_drivers")
        return render(request, "transport/admin_driver_form.html", {"form": form, "title": "Register Driver"})


class AdminDriverUpdateView(LoginRequiredMixin, View):
    def get(self, request, pk):
        if not _is_transport_admin(request.user):
            raise PermissionDenied("Unauthorized.")
        driver = get_object_or_404(Driver, pk=pk)
        form = DriverForm(instance=driver)
        return render(request, "transport/admin_driver_form.html", {"form": form, "driver": driver, "title": f"Edit Driver {driver.name}"})

    def post(self, request, pk):
        if not _is_transport_admin(request.user):
            raise PermissionDenied("Unauthorized.")
        driver = get_object_or_404(Driver, pk=pk)
        form = DriverForm(request.POST, instance=driver)
        if form.is_valid():
            d = form.save()
            messages.success(request, f"Driver {d.name} updated.")
            return redirect("transport:admin_drivers")
        return render(request, "transport/admin_driver_form.html", {"form": form, "driver": driver, "title": f"Edit Driver {driver.name}"})


class AdminConductorListView(LoginRequiredMixin, View):
    def get(self, request):
        if not _is_transport_admin(request.user):
            raise PermissionDenied("Unauthorized.")
        conductors = Conductor.objects.all().select_related("assigned_vehicle", "assigned_route").order_by("name")
        return render(request, "transport/admin_conductor_list.html", {"conductors": conductors})


class AdminConductorCreateView(LoginRequiredMixin, View):
    def get(self, request):
        if not _is_transport_admin(request.user):
            raise PermissionDenied("Unauthorized.")
        form = ConductorForm()
        return render(request, "transport/admin_conductor_form.html", {"form": form, "title": "Register Conductor"})

    def post(self, request):
        if not _is_transport_admin(request.user):
            raise PermissionDenied("Unauthorized.")
        form = ConductorForm(request.POST)
        if form.is_valid():
            c = form.save()
            messages.success(request, f"Conductor {c.name} registered.")
            return redirect("transport:admin_conductors")
        return render(request, "transport/admin_conductor_form.html", {"form": form, "title": "Register Conductor"})


class AdminConductorUpdateView(LoginRequiredMixin, View):
    def get(self, request, pk):
        if not _is_transport_admin(request.user):
            raise PermissionDenied("Unauthorized.")
        conductor = get_object_or_404(Conductor, pk=pk)
        form = ConductorForm(instance=conductor)
        return render(request, "transport/admin_conductor_form.html", {"form": form, "conductor": conductor, "title": f"Edit Conductor {conductor.name}"})

    def post(self, request, pk):
        if not _is_transport_admin(request.user):
            raise PermissionDenied("Unauthorized.")
        conductor = get_object_or_404(Conductor, pk=pk)
        form = ConductorForm(request.POST, instance=conductor)
        if form.is_valid():
            c = form.save()
            messages.success(request, f"Conductor {c.name} updated.")
            return redirect("transport:admin_conductors")
        return render(request, "transport/admin_conductor_form.html", {"form": form, "conductor": conductor, "title": f"Edit Conductor {conductor.name}"})


# ----------------------------------------------------------------
# APPLICATION REVIEW & APPROVAL
# ----------------------------------------------------------------
class AdminApplicationListView(LoginRequiredMixin, View):
    def get(self, request):
        if not _is_transport_admin(request.user):
            raise PermissionDenied("Unauthorized.")
        qs = TransportApplication.objects.all().select_related("student", "route", "stop").order_by("-application_date")
        status_filter = request.GET.get("status", "").strip()
        route_filter = request.GET.get("route", "").strip()
        q = request.GET.get("q", "").strip()

        if status_filter:
            qs = qs.filter(status=status_filter)
        if route_filter:
            qs = qs.filter(route_id=route_filter)
        if q:
            qs = qs.filter(Q(application_id__icontains=q) | Q(student__name__icontains=q) | Q(student__roll_no__icontains=q))

        paginator = Paginator(qs, 20)
        page_obj = paginator.get_page(request.GET.get("page", 1))
        routes = Route.objects.filter(is_active=True).order_by("code")
        return render(request, "transport/admin_application_list.html", {
            "page_obj": page_obj,
            "status": status_filter,
            "route": route_filter,
            "q": q,
            "routes": routes,
        })


class AdminApplicationReviewView(LoginRequiredMixin, View):
    def post(self, request, pk):
        if not _is_transport_admin(request.user):
            raise PermissionDenied("Unauthorized.")
        app = get_object_or_404(TransportApplication.objects.select_related("student", "student__user", "route"), pk=pk)
        form = ApplicationReviewForm(request.POST)
        if form.is_valid():
            action = form.cleaned_data["action"]
            reason = form.cleaned_data.get("rejection_reason", "")
            remarks = form.cleaned_data.get("remarks", "")

            app.status = action
            app.rejection_reason = reason
            app.remarks = remarks
            app.reviewed_by = request.user
            app.reviewed_at = timezone.now()
            app.save()

            if app.student.user:
                notify_transport_event(
                    app.student.user,
                    title=f"Transport Application {app.get_status_display()}",
                    message=f"Your request {app.application_id} for Route {app.route.code} has been {app.get_status_display().lower()}.",
                    link=f"/transport/applications/{app.pk}/",
                )

            messages.success(request, f"Application {app.application_id} marked as {app.get_status_display()}.")
            return redirect("transport:application_detail", pk=app.pk)

        messages.error(request, "Validation error occurred during application review.")
        return redirect("transport:application_detail", pk=app.pk)


# ----------------------------------------------------------------
# ALLOCATIONS & PASSES
# ----------------------------------------------------------------
class AdminAllocationListView(LoginRequiredMixin, View):
    def get(self, request):
        if not _is_transport_admin(request.user):
            raise PermissionDenied("Unauthorized.")
        qs = TransportAllocation.objects.all().select_related("student", "student__course", "vehicle", "route", "stop").order_by("-start_date")
        route_filter = request.GET.get("route", "").strip()
        vehicle_filter = request.GET.get("vehicle", "").strip()
        q = request.GET.get("q", "").strip()

        if route_filter:
            qs = qs.filter(route_id=route_filter)
        if vehicle_filter:
            qs = qs.filter(vehicle_id=vehicle_filter)
        if q:
            qs = qs.filter(Q(student__name__icontains=q) | Q(student__roll_no__icontains=q) | Q(allocation_id__icontains=q))

        paginator = Paginator(qs, 20)
        page_obj = paginator.get_page(request.GET.get("page", 1))
        routes = Route.objects.filter(is_active=True).order_by("code")
        vehicles = Vehicle.objects.filter(status="ACTIVE").order_by("vehicle_number")
        return render(request, "transport/admin_allocation_list.html", {
            "page_obj": page_obj,
            "routes": routes,
            "vehicles": vehicles,
            "q": q,
            "route": route_filter,
            "vehicle": vehicle_filter,
        })


class AdminAllocationCreateView(LoginRequiredMixin, View):
    def get(self, request):
        if not _is_transport_admin(request.user):
            raise PermissionDenied("Unauthorized.")
        form = TransportAllocationForm()
        return render(request, "transport/admin_allocation_form.html", {"form": form, "title": "Allocate Student to Bus"})

    def post(self, request):
        if not _is_transport_admin(request.user):
            raise PermissionDenied("Unauthorized.")
        form = TransportAllocationForm(request.POST)
        if form.is_valid():
            with transaction.atomic():
                alloc = form.save(commit=False)
                alloc.allocated_by = request.user

                # Verify vehicle capacity
                vehicle = alloc.vehicle
                if vehicle.allocated_count >= vehicle.seating_capacity:
                    form.add_error("vehicle", f"Vehicle {vehicle.vehicle_number} has reached maximum seating capacity ({vehicle.seating_capacity}).")
                    return render(request, "transport/admin_allocation_form.html", {"form": form, "title": "Allocate Student to Bus"})

                alloc.save()

                # Automatically issue bus pass if requested
                issue_pass = request.POST.get("issue_pass") == "1"
                if issue_pass or True:
                    today = timezone.now().date()
                    expiry = today.replace(year=today.year + 1)
                    TransportPass.objects.get_or_create(
                        student=alloc.student,
                        allocation=alloc,
                        defaults={
                            "academic_year": alloc.academic_year,
                            "issue_date": today,
                            "expiry_date": expiry,
                            "status": "ACTIVE",
                            "issued_by": request.user,
                        }
                    )

                if alloc.student.user:
                    notify_transport_event(
                        alloc.student.user,
                        title="Bus Transport Allocated",
                        message=f"You are allocated to Bus {vehicle.vehicle_number} on Route {alloc.route.code} (Stop: {alloc.stop.stop_name}).",
                        link="/transport/portal/",
                    )

            messages.success(request, f"Student {alloc.student.name} allocated to Bus {alloc.vehicle.vehicle_number} successfully!")
            return redirect("transport:admin_allocation_detail", pk=alloc.pk)

        return render(request, "transport/admin_allocation_form.html", {"form": form, "title": "Allocate Student to Bus"})


class AdminAllocationDetailView(LoginRequiredMixin, View):
    def get(self, request, pk):
        if not _is_transport_admin(request.user):
            raise PermissionDenied("Unauthorized.")
        alloc = get_object_or_404(TransportAllocation.objects.select_related("student", "student__course", "vehicle", "route", "stop", "allocated_by"), pk=pk)
        pass_obj = getattr(alloc, "bus_pass", None)
        return render(request, "transport/admin_allocation_detail.html", {"allocation": alloc, "pass": pass_obj})


class AdminAllocationCancelView(LoginRequiredMixin, View):
    def post(self, request, pk):
        if not _is_transport_admin(request.user):
            raise PermissionDenied("Unauthorized.")
        alloc = get_object_or_404(TransportAllocation, pk=pk)
        with transaction.atomic():
            alloc.status = "CANCELLED"
            alloc.end_date = timezone.now().date()
            alloc.save()
            if hasattr(alloc, "bus_pass"):
                alloc.bus_pass.status = "CANCELLED"
                alloc.bus_pass.save()

            if alloc.student.user:
                notify_transport_event(
                    alloc.student.user,
                    title="Transport Allocation Cancelled",
                    message=f"Your allocation on Route {alloc.route.code} has been cancelled.",
                    link="/transport/portal/",
                )

        messages.info(request, f"Allocation {alloc.allocation_id} cancelled.")
        return redirect("transport:admin_allocations")


class AdminPassListView(LoginRequiredMixin, View):
    def get(self, request):
        if not _is_transport_admin(request.user):
            raise PermissionDenied("Unauthorized.")
        qs = TransportPass.objects.all().select_related("student", "allocation__vehicle", "allocation__route", "allocation__stop").order_by("-issue_date")
        q = request.GET.get("q", "").strip()
        status_filter = request.GET.get("status", "").strip()
        if q:
            qs = qs.filter(Q(pass_number__icontains=q) | Q(student__name__icontains=q) | Q(student__roll_no__icontains=q))
        if status_filter:
            qs = qs.filter(status=status_filter)
        paginator = Paginator(qs, 20)
        page_obj = paginator.get_page(request.GET.get("page", 1))
        return render(request, "transport/admin_pass_list.html", {"page_obj": page_obj, "q": q, "status": status_filter})


class AdminPassDetailView(LoginRequiredMixin, View):
    def get(self, request, pk):
        if not _is_transport_admin(request.user):
            raise PermissionDenied("Unauthorized.")
        pass_obj = get_object_or_404(TransportPass.objects.select_related("student", "student__course", "allocation__vehicle", "allocation__route", "allocation__stop"), pk=pk)
        return render(request, "transport/admin_pass_detail.html", {"pass": pass_obj})


class AdminPassPdfDownloadView(LoginRequiredMixin, View):
    def get(self, request, pk):
        if not _is_transport_admin(request.user):
            raise PermissionDenied("Unauthorized.")
        pass_obj = get_object_or_404(TransportPass, pk=pk)
        return generate_single_pass_pdf(pass_obj)


# ----------------------------------------------------------------
# ATTENDANCE MANAGEMENT
# ----------------------------------------------------------------
class AdminAttendanceView(LoginRequiredMixin, View):
    def get(self, request):
        if not _is_transport_admin(request.user):
            raise PermissionDenied("Unauthorized.")
        selected_date_str = request.GET.get("date", timezone.now().date().isoformat())
        trip_type = request.GET.get("trip_type", "MORNING")
        route_id = request.GET.get("route", "")

        try:
            selected_date = timezone.datetime.strptime(selected_date_str, "%Y-%m-%d").date()
        except ValueError:
            selected_date = timezone.now().date()

        records_qs = TransportAttendance.objects.filter(date=selected_date, trip_type=trip_type).select_related("student", "route", "vehicle", "boarding_stop")
        if route_id:
            records_qs = records_qs.filter(route_id=route_id)

        routes = Route.objects.filter(is_active=True).order_by("code")
        return render(request, "transport/admin_attendance.html", {
            "records": records_qs,
            "selected_date": selected_date.isoformat(),
            "trip_type": trip_type,
            "route_id": route_id,
            "routes": routes,
        })


class AdminMarkAttendanceView(LoginRequiredMixin, View):
    def get(self, request):
        if not _is_transport_admin(request.user):
            raise PermissionDenied("Unauthorized.")
        route_id = request.GET.get("route")
        trip_type = request.GET.get("trip_type", "MORNING")
        selected_date_str = request.GET.get("date", timezone.now().date().isoformat())
        routes = Route.objects.filter(is_active=True).select_related("assigned_vehicle").order_by("code")

        students_roster = []
        route = None
        if route_id:
            route = get_object_or_404(Route, pk=route_id)
            allocs = TransportAllocation.objects.filter(route=route, status="ACTIVE").select_related("student", "stop", "vehicle")
            for a in allocs:
                existing = TransportAttendance.objects.filter(student=a.student, date=selected_date_str, trip_type=trip_type).first()
                students_roster.append({
                    "allocation": a,
                    "student": a.student,
                    "stop": a.stop,
                    "vehicle": a.vehicle,
                    "existing_status": existing.status if existing else "PRESENT",
                })

        return render(request, "transport/admin_attendance_mark.html", {
            "routes": routes,
            "route": route,
            "route_id": route_id,
            "trip_type": trip_type,
            "selected_date": selected_date_str,
            "roster": students_roster,
        })

    def post(self, request):
        if not _is_transport_admin(request.user):
            raise PermissionDenied("Unauthorized.")
        route_id = request.POST.get("route")
        trip_type = request.POST.get("trip_type", "MORNING")
        selected_date_str = request.POST.get("date")

        route = get_object_or_404(Route, pk=route_id)
        allocs = TransportAllocation.objects.filter(route=route, status="ACTIVE").select_related("student", "vehicle", "stop")

        saved_count = 0
        with transaction.atomic():
            for a in allocs:
                status_val = request.POST.get(f"status_{a.student.id}", "PRESENT")
                TransportAttendance.objects.update_or_create(
                    student=a.student,
                    date=selected_date_str,
                    trip_type=trip_type,
                    defaults={
                        "vehicle": a.vehicle,
                        "route": route,
                        "boarding_stop": a.stop,
                        "status": status_val,
                        "marked_by": request.user,
                    }
                )
                saved_count += 1

        messages.success(request, f"Attendance marked for {saved_count} students on Route {route.code} ({trip_type}).")
        return redirect(f"/transport/admin/attendance/?date={selected_date_str}&trip_type={trip_type}&route={route.id}")


# ----------------------------------------------------------------
# VEHICLE MAINTENANCE VIEWS
# ----------------------------------------------------------------
class AdminMaintenanceListView(LoginRequiredMixin, View):
    def get(self, request):
        if not _is_transport_admin(request.user):
            raise PermissionDenied("Unauthorized.")
        records = VehicleMaintenance.objects.all().select_related("vehicle").order_by("-service_date")
        return render(request, "transport/admin_maintenance_list.html", {"records": records})


class AdminMaintenanceCreateView(LoginRequiredMixin, View):
    def get(self, request):
        if not _is_transport_admin(request.user):
            raise PermissionDenied("Unauthorized.")
        form = VehicleMaintenanceForm()
        return render(request, "transport/admin_maintenance_form.html", {"form": form, "title": "Log Vehicle Service / Maintenance"})

    def post(self, request):
        if not _is_transport_admin(request.user):
            raise PermissionDenied("Unauthorized.")
        form = VehicleMaintenanceForm(request.POST)
        if form.is_valid():
            m = form.save(commit=False)
            m.logged_by = request.user
            m.save()
            messages.success(request, f"Maintenance record logged for {m.vehicle.vehicle_number}.")
            return redirect("transport:admin_maintenance")
        return render(request, "transport/admin_maintenance_form.html", {"form": form, "title": "Log Vehicle Service / Maintenance"})


class AdminMaintenanceUpdateView(LoginRequiredMixin, View):
    def get(self, request, pk):
        if not _is_transport_admin(request.user):
            raise PermissionDenied("Unauthorized.")
        rec = get_object_or_404(VehicleMaintenance, pk=pk)
        form = VehicleMaintenanceForm(instance=rec)
        return render(request, "transport/admin_maintenance_form.html", {"form": form, "maintenance": rec, "title": f"Update Service Record #{rec.pk}"})

    def post(self, request, pk):
        if not _is_transport_admin(request.user):
            raise PermissionDenied("Unauthorized.")
        rec = get_object_or_404(VehicleMaintenance, pk=pk)
        form = VehicleMaintenanceForm(request.POST, instance=rec)
        if form.is_valid():
            form.save()
            messages.success(request, "Service record updated.")
            return redirect("transport:admin_maintenance")
        return render(request, "transport/admin_maintenance_form.html", {"form": form, "maintenance": rec, "title": f"Update Service Record #{rec.pk}"})


# ----------------------------------------------------------------
# COMPLAINTS & INCIDENTS
# ----------------------------------------------------------------
class AdminComplaintListView(LoginRequiredMixin, View):
    def get(self, request):
        if not _is_transport_admin(request.user):
            raise PermissionDenied("Unauthorized.")
        complaints = TransportComplaint.objects.all().select_related("student", "route", "vehicle", "assigned_staff").order_by("-created_at")
        return render(request, "transport/admin_complaint_list.html", {"complaints": complaints})


class AdminComplaintDetailView(LoginRequiredMixin, View):
    def get(self, request, pk):
        if not _is_transport_admin(request.user):
            raise PermissionDenied("Unauthorized.")
        comp = get_object_or_404(TransportComplaint.objects.select_related("student", "route", "vehicle", "assigned_staff"), pk=pk)
        form = AdminComplaintUpdateForm(instance=comp)
        return render(request, "transport/admin_complaint_detail.html", {"complaint": comp, "form": form})

    def post(self, request, pk):
        if not _is_transport_admin(request.user):
            raise PermissionDenied("Unauthorized.")
        comp = get_object_or_404(TransportComplaint.objects.select_related("student", "student__user"), pk=pk)
        form = AdminComplaintUpdateForm(request.POST, instance=comp)
        if form.is_valid():
            c = form.save(commit=False)
            if c.status in ("RESOLVED", "CLOSED") and not c.resolved_at:
                c.resolved_at = timezone.now()
            c.save()

            if c.student.user:
                notify_transport_event(
                    c.student.user,
                    title=f"Transport Complaint {c.get_status_display()}",
                    message=f"Complaint {c.complaint_id} status updated to {c.get_status_display()}.",
                    link=f"/transport/complaints/{c.pk}/",
                )

            messages.success(request, f"Complaint {c.complaint_id} updated.")
            return redirect("transport:admin_complaint_detail", pk=c.pk)
        return render(request, "transport/admin_complaint_detail.html", {"complaint": comp, "form": form})


class AdminIncidentListView(LoginRequiredMixin, View):
    def get(self, request):
        if not _is_transport_admin(request.user):
            raise PermissionDenied("Unauthorized.")
        incidents = TransportIncident.objects.all().select_related("vehicle", "route", "reported_by").order_by("-date")
        return render(request, "transport/admin_incident_list.html", {"incidents": incidents})


class AdminIncidentCreateView(LoginRequiredMixin, View):
    def get(self, request):
        if not _is_transport_admin(request.user):
            raise PermissionDenied("Unauthorized.")
        form = TransportIncidentForm()
        return render(request, "transport/admin_incident_form.html", {"form": form, "title": "Log Transport Incident"})

    def post(self, request):
        if not _is_transport_admin(request.user):
            raise PermissionDenied("Unauthorized.")
        form = TransportIncidentForm(request.POST)
        if form.is_valid():
            inc = form.save(commit=False)
            inc.reported_by = request.user
            inc.save()
            messages.success(request, f"Incident {inc.incident_id} recorded.")
            return redirect("transport:admin_incidents")
        return render(request, "transport/admin_incident_form.html", {"form": form, "title": "Log Transport Incident"})


# ----------------------------------------------------------------
# TRANSPORT FEES INTEGRATION VIEWS
# ----------------------------------------------------------------
class AdminTransportFeeListView(LoginRequiredMixin, View):
    def get(self, request):
        if not _is_transport_admin(request.user):
            raise PermissionDenied("Unauthorized.")
        fees_data = get_admin_transport_fees_summary()
        return render(request, "transport/admin_fees.html", {"fees_data": fees_data})


class AdminCreateTransportFeeView(LoginRequiredMixin, View):
    def get(self, request):
        if not _is_transport_admin(request.user):
            raise PermissionDenied("Unauthorized.")
        form = TransportFeeDemandForm()
        return render(request, "transport/admin_fee_form.html", {"form": form, "title": "Issue Transport Fee Demand"})

    def post(self, request):
        if not _is_transport_admin(request.user):
            raise PermissionDenied("Unauthorized.")
        form = TransportFeeDemandForm(request.POST)
        if form.is_valid():
            student = form.cleaned_data["student"]
            fee = FeeRecord.objects.create(
                student=student,
                fee_type="TRANSPORT",
                title=form.cleaned_data["title"],
                academic_year=form.cleaned_data["academic_year"],
                semester=form.cleaned_data.get("semester"),
                amount=form.cleaned_data["amount"],
                due_date=form.cleaned_data.get("due_date"),
                remarks=form.cleaned_data.get("remarks", ""),
                status="PENDING",
            )
            if student.user:
                notify_transport_event(
                    student.user,
                    title="Transport Fee Demand Issued",
                    message=f"A transport fee record of ₹{fee.amount} has been added to your ledger.",
                    link="/transport/fees/",
                )
            messages.success(request, f"Transport fee demand of ₹{fee.amount} issued for {student.name}.")
            return redirect("transport:admin_fees")
        return render(request, "transport/admin_fee_form.html", {"form": form, "title": "Issue Transport Fee Demand"})


class AdminRecordTransportPaymentView(LoginRequiredMixin, View):
    def get(self, request, fee_id):
        if not _is_transport_admin(request.user):
            raise PermissionDenied("Unauthorized.")
        fee = get_object_or_404(FeeRecord, pk=fee_id, fee_type="TRANSPORT")
        form = TransportFeePaymentForm(initial={"amount": fee.balance_amount})
        return render(request, "transport/admin_fee_payment_form.html", {"fee": fee, "form": form})

    def post(self, request, fee_id):
        if not _is_transport_admin(request.user):
            raise PermissionDenied("Unauthorized.")
        fee = get_object_or_404(FeeRecord, pk=fee_id, fee_type="TRANSPORT")
        form = TransportFeePaymentForm(request.POST)
        if form.is_valid():
            amt = form.cleaned_data["amount"]
            if amt > fee.balance_amount:
                form.add_error("amount", f"Amount cannot exceed outstanding balance of ₹{fee.balance_amount}.")
                return render(request, "transport/admin_fee_payment_form.html", {"fee": fee, "form": form})

            import uuid
            rcpt = f"TR-RCPT-{timezone.now().strftime('%Y%m')}-{uuid.uuid4().hex[:6].upper()}"
            with transaction.atomic():
                payment = FeePayment.objects.create(
                    fee_record=fee,
                    receipt_number=rcpt,
                    amount=amt,
                    payment_date=form.cleaned_data["payment_date"],
                    payment_mode=form.cleaned_data["payment_mode"],
                    reference_number=form.cleaned_data.get("reference_number", ""),
                    remarks=form.cleaned_data.get("remarks", ""),
                )
                fee.refresh_from_db()
                if fee.student.user:
                    notify_transport_event(
                        fee.student.user,
                        title="Transport Fee Payment Received",
                        message=f"Receipt {payment.receipt_number} generated for payment of ₹{payment.amount}.",
                        link="/transport/fees/",
                    )

            messages.success(request, f"Payment of ₹{payment.amount} recorded! Receipt: {payment.receipt_number}")
            return redirect("transport:admin_fees")
        return render(request, "transport/admin_fee_payment_form.html", {"fee": fee, "form": form})
