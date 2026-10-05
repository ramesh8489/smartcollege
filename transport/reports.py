import io
from decimal import Decimal
from django.http import HttpResponse
from django.shortcuts import render
from django.views import View
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.utils import timezone
from django.db.models import Count, Q, Sum

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT

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
from fees.models import FeeRecord
from .services import get_admin_transport_fees_summary


def _is_transport_authorized(user):
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser or user.is_staff:
        return True
    return hasattr(user, "transport_staff_profile") and user.transport_staff_profile.is_active


# ================================================================
# EXCEL STYLING HELPERS
# ================================================================
def _apply_excel_header_style(ws, headers):
    header_fill = PatternFill(start_color="1E293B", end_color="1E293B", fill_type="solid")
    header_font = Font(name="Arial", size=10, bold=True, color="FFFFFF")
    thin_border = Border(
        left=Side(style="thin", color="CBD5E1"),
        right=Side(style="thin", color="CBD5E1"),
        top=Side(style="thin", color="CBD5E1"),
        bottom=Side(style="thin", color="CBD5E1"),
    )

    ws.append(headers)
    for col_idx in range(1, len(headers) + 1):
        cell = ws.cell(row=1, column=col_idx)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = thin_border
    ws.row_dimensions[1].height = 26


def _autofit_excel_columns(ws, min_width=12, max_width=45):
    for col in ws.columns:
        col_letter = get_column_letter(col[0].column)
        max_len = 0
        for cell in col:
            val = str(cell.value or "")
            if len(val) > max_len:
                max_len = len(val)
        ws.column_dimensions[col_letter].width = max(min(max_len + 4, max_width), min_width)


# ================================================================
# PDF STYLING HELPERS
# ================================================================
def _build_pdf_report(title, headers, data_rows, filename, is_landscape=False, col_widths=None):
    buffer = io.BytesIO()
    page_size = landscape(A4) if is_landscape else A4
    doc = SimpleDocTemplate(
        buffer,
        pagesize=page_size,
        leftMargin=24,
        rightMargin=24,
        topMargin=24,
        bottomMargin=24,
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "ReportTitle",
        parent=styles["Heading1"],
        fontName="Helvetica-Bold",
        fontSize=14,
        leading=18,
        textColor=colors.HexColor("#0F172A"),
        alignment=TA_CENTER,
    )
    sub_style = ParagraphStyle(
        "ReportSubtitle",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9,
        leading=12,
        textColor=colors.HexColor("#64748B"),
        alignment=TA_CENTER,
    )
    cell_style = ParagraphStyle(
        "CellText",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8,
        leading=10,
        textColor=colors.HexColor("#1E293B"),
    )
    header_cell_style = ParagraphStyle(
        "HeaderCellText",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=8.5,
        leading=11,
        textColor=colors.white,
        alignment=TA_CENTER,
    )

    elements = []
    elements.append(Paragraph("SMART COLLEGE &middot; TRANSPORT MANAGEMENT SYSTEM", sub_style))
    elements.append(Paragraph(title.upper(), title_style))
    now_str = timezone.now().strftime("%d %b %Y, %I:%M %p")
    elements.append(Paragraph(f"Generated on {now_str} &middot; Total Records: {len(data_rows)}", sub_style))
    elements.append(Spacer(1, 14))

    table_data = []
    # Header row
    table_data.append([Paragraph(h, header_cell_style) for h in headers])

    # Data rows
    for row in data_rows:
        row_cells = []
        for c in row:
            row_cells.append(Paragraph(str(c if c is not None else "-"), cell_style))
        table_data.append(row_cells)

    pdf_table = Table(table_data, colWidths=col_widths, repeatRows=1)
    pdf_table.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1E293B")),
            ("ALIGN", (0, 0), (-1, -1), "LEFT"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
            ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#94A3B8")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ])
    )
    elements.append(pdf_table)

    doc.build(elements)
    buffer.seek(0)

    response = HttpResponse(buffer.getvalue(), content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


# ================================================================
# REPORTS HUB VIEW
# ================================================================
class TransportReportsHubView(LoginRequiredMixin, View):
    def get(self, request):
        if not _is_transport_authorized(request.user):
            raise PermissionDenied("Access restricted to transport administrators.")
        return render(request, "transport/admin_reports_hub.html")


# ================================================================
# 1. VEHICLE LIST REPORT
# ================================================================
class ExportVehicleExcelView(LoginRequiredMixin, View):
    def get(self, request):
        if not _is_transport_authorized(request.user):
            raise PermissionDenied("Unauthorized.")
        wb = Workbook()
        ws = wb.active
        ws.title = "Vehicles"
        headers = ["Vehicle No", "Registration No", "Bus Name", "Type", "Capacity", "Allocated", "Available", "Status", "Insurance Expiry", "Fitness Expiry"]
        _apply_excel_header_style(ws, headers)
        for v in Vehicle.objects.all().order_by("vehicle_number"):
            ws.append([
                v.vehicle_number, v.registration_number, v.bus_name, v.get_vehicle_type_display(),
                v.seating_capacity, v.allocated_count, v.available_seats, v.get_status_display(),
                str(v.insurance_expiry or "-"), str(v.fitness_expiry or "-")
            ])
        _autofit_excel_columns(ws)
        resp = HttpResponse(content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        resp["Content-Disposition"] = 'attachment; filename="transport_vehicles.xlsx"'
        wb.save(resp)
        return resp


class ExportVehiclePdfView(LoginRequiredMixin, View):
    def get(self, request):
        if not _is_transport_authorized(request.user):
            raise PermissionDenied("Unauthorized.")
        headers = ["Vehicle No", "Reg No", "Bus Name", "Type", "Cap", "Alloc", "Avail", "Status", "Insurance", "Fitness"]
        rows = []
        for v in Vehicle.objects.all().order_by("vehicle_number"):
            rows.append([
                v.vehicle_number, v.registration_number, v.bus_name, v.get_vehicle_type_display(),
                v.seating_capacity, v.allocated_count, v.available_seats, v.get_status_display(),
                str(v.insurance_expiry or "-"), str(v.fitness_expiry or "-")
            ])
        return _build_pdf_report("Vehicle Roster & Fleet Report", headers, rows, "transport_vehicles.pdf", is_landscape=True)


# ================================================================
# 2. ROUTE LIST REPORT
# ================================================================
class ExportRouteExcelView(LoginRequiredMixin, View):
    def get(self, request):
        if not _is_transport_authorized(request.user):
            raise PermissionDenied("Unauthorized.")
        wb = Workbook()
        ws = wb.active
        ws.title = "Routes"
        headers = ["Code", "Route Name", "Start Point", "Destination", "Assigned Vehicle", "Stops", "Students", "Active"]
        _apply_excel_header_style(ws, headers)
        for r in Route.objects.all().select_related("assigned_vehicle").order_by("code"):
            ws.append([
                r.code, r.name, r.start_point, r.destination,
                r.assigned_vehicle.vehicle_number if r.assigned_vehicle else "-",
                r.stop_count, r.total_students, "Yes" if r.is_active else "No"
            ])
        _autofit_excel_columns(ws)
        resp = HttpResponse(content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        resp["Content-Disposition"] = 'attachment; filename="transport_routes.xlsx"'
        wb.save(resp)
        return resp


class ExportRoutePdfView(LoginRequiredMixin, View):
    def get(self, request):
        if not _is_transport_authorized(request.user):
            raise PermissionDenied("Unauthorized.")
        headers = ["Code", "Route Name", "Start Point", "Destination", "Vehicle", "Stops", "Students", "Status"]
        rows = []
        for r in Route.objects.all().select_related("assigned_vehicle").order_by("code"):
            rows.append([
                r.code, r.name, r.start_point, r.destination,
                r.assigned_vehicle.vehicle_number if r.assigned_vehicle else "-",
                r.stop_count, r.total_students, "Active" if r.is_active else "Inactive"
            ])
        return _build_pdf_report("Transport Routes Schedule", headers, rows, "transport_routes.pdf", is_landscape=True)


# ================================================================
# 3. STOP LIST REPORT
# ================================================================
class ExportStopExcelView(LoginRequiredMixin, View):
    def get(self, request):
        if not _is_transport_authorized(request.user):
            raise PermissionDenied("Unauthorized.")
        wb = Workbook()
        ws = wb.active
        ws.title = "Stops"
        headers = ["Route Code", "Route Name", "Order", "Stop Name", "Stop Code", "Pickup Time", "Drop Time", "Distance (km)", "Fare (₹)"]
        _apply_excel_header_style(ws, headers)
        for s in Stop.objects.all().select_related("route").order_by("route__code", "stop_order"):
            ws.append([
                s.route.code, s.route.name, s.stop_order, s.stop_name, s.stop_code or "-",
                s.pickup_time.strftime("%I:%M %p"), s.drop_time.strftime("%I:%M %p"),
                float(s.distance_km) if s.distance_km else "-", float(s.fare_amount)
            ])
        _autofit_excel_columns(ws)
        resp = HttpResponse(content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        resp["Content-Disposition"] = 'attachment; filename="transport_stops.xlsx"'
        wb.save(resp)
        return resp


class ExportStopPdfView(LoginRequiredMixin, View):
    def get(self, request):
        if not _is_transport_authorized(request.user):
            raise PermissionDenied("Unauthorized.")
        headers = ["Route", "Order", "Stop Name", "Code", "Pickup Time", "Drop Time", "Distance", "Fare (₹)"]
        rows = []
        for s in Stop.objects.all().select_related("route").order_by("route__code", "stop_order"):
            rows.append([
                s.route.code, s.stop_order, s.stop_name, s.stop_code or "-",
                s.pickup_time.strftime("%I:%M %p"), s.drop_time.strftime("%I:%M %p"),
                f"{s.distance_km} km" if s.distance_km else "-", f"₹{s.fare_amount}"
            ])
        return _build_pdf_report("Route Stops & Timing Directory", headers, rows, "transport_stops.pdf", is_landscape=True)


# ================================================================
# 4. DRIVER & CONDUCTOR LIST REPORT
# ================================================================
class ExportDriverExcelView(LoginRequiredMixin, View):
    def get(self, request):
        if not _is_transport_authorized(request.user):
            raise PermissionDenied("Unauthorized.")
        wb = Workbook()
        ws = wb.active
        ws.title = "Drivers"
        headers = ["Emp ID", "Driver Name", "Phone", "Licence Number", "Licence Expiry", "Assigned Bus", "Active"]
        _apply_excel_header_style(ws, headers)
        for d in Driver.objects.all().select_related("assigned_vehicle").order_by("name"):
            ws.append([
                d.employee_id, d.name, d.phone, d.licence_number, str(d.licence_expiry),
                d.assigned_vehicle.vehicle_number if d.assigned_vehicle else "-",
                "Yes" if d.is_active else "No"
            ])
        _autofit_excel_columns(ws)
        resp = HttpResponse(content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        resp["Content-Disposition"] = 'attachment; filename="transport_drivers.xlsx"'
        wb.save(resp)
        return resp


class ExportDriverPdfView(LoginRequiredMixin, View):
    def get(self, request):
        if not _is_transport_authorized(request.user):
            raise PermissionDenied("Unauthorized.")
        headers = ["Emp ID", "Driver Name", "Phone", "Licence No", "Expiry Date", "Assigned Bus", "Status"]
        rows = []
        for d in Driver.objects.all().select_related("assigned_vehicle").order_by("name"):
            status_str = "Expired" if d.is_licence_expired else ("Expiring Soon" if d.is_licence_expiring_soon else "Valid")
            rows.append([
                d.employee_id, d.name, d.phone, d.licence_number, str(d.licence_expiry),
                d.assigned_vehicle.vehicle_number if d.assigned_vehicle else "-", status_str
            ])
        return _build_pdf_report("Transport Drivers & Licence Register", headers, rows, "transport_drivers.pdf", is_landscape=True)


# ================================================================
# 5. STUDENT ALLOCATION REPORT
# ================================================================
class ExportAllocationExcelView(LoginRequiredMixin, View):
    def get(self, request):
        if not _is_transport_authorized(request.user):
            raise PermissionDenied("Unauthorized.")
        wb = Workbook()
        ws = wb.active
        ws.title = "Allocations"
        headers = ["Alloc ID", "Roll No", "Student Name", "Course", "Year", "Route", "Stop", "Vehicle", "Seat No", "Status", "Start Date"]
        _apply_excel_header_style(ws, headers)
        allocs = TransportAllocation.objects.all().select_related("student", "student__course", "route", "stop", "vehicle").order_by("route__code", "student__name")
        for a in allocs:
            ws.append([
                a.allocation_id, a.student.roll_no, a.student.name,
                a.student.course.name if a.student.course else "-", a.student.year,
                a.route.code, a.stop.stop_name, a.vehicle.vehicle_number, a.seat_number or "-",
                a.get_status_display(), str(a.start_date)
            ])
        _autofit_excel_columns(ws)
        resp = HttpResponse(content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        resp["Content-Disposition"] = 'attachment; filename="transport_allocations.xlsx"'
        wb.save(resp)
        return resp


class ExportAllocationPdfView(LoginRequiredMixin, View):
    def get(self, request):
        if not _is_transport_authorized(request.user):
            raise PermissionDenied("Unauthorized.")
        headers = ["Alloc ID", "Roll No", "Student Name", "Course", "Route", "Stop", "Vehicle", "Seat", "Status"]
        rows = []
        allocs = TransportAllocation.objects.all().select_related("student", "student__course", "route", "stop", "vehicle").order_by("route__code", "student__name")
        for a in allocs:
            rows.append([
                a.allocation_id, a.student.roll_no, a.student.name,
                a.student.course.name if a.student.course else "-",
                a.route.code, a.stop.stop_name, a.vehicle.vehicle_number, a.seat_number or "-",
                a.get_status_display()
            ])
        return _build_pdf_report("Student Transport Allocation Roster", headers, rows, "transport_allocations.pdf", is_landscape=True)


# ================================================================
# 6. VEHICLE OCCUPANCY REPORT
# ================================================================
class ExportOccupancyExcelView(LoginRequiredMixin, View):
    def get(self, request):
        if not _is_transport_authorized(request.user):
            raise PermissionDenied("Unauthorized.")
        wb = Workbook()
        ws = wb.active
        ws.title = "Occupancy"
        headers = ["Vehicle No", "Registration No", "Bus Name", "Capacity", "Allocated Students", "Available Seats", "Occupancy %", "Status"]
        _apply_excel_header_style(ws, headers)
        for v in Vehicle.objects.all().order_by("vehicle_number"):
            ws.append([
                v.vehicle_number, v.registration_number, v.bus_name,
                v.seating_capacity, v.allocated_count, v.available_seats,
                f"{v.occupancy_percentage}%", v.get_status_display()
            ])
        _autofit_excel_columns(ws)
        resp = HttpResponse(content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        resp["Content-Disposition"] = 'attachment; filename="transport_occupancy.xlsx"'
        wb.save(resp)
        return resp


class ExportOccupancyPdfView(LoginRequiredMixin, View):
    def get(self, request):
        if not _is_transport_authorized(request.user):
            raise PermissionDenied("Unauthorized.")
        headers = ["Vehicle No", "Reg No", "Bus Name", "Capacity", "Allocated", "Available", "Occupancy %", "Status"]
        rows = []
        for v in Vehicle.objects.all().order_by("vehicle_number"):
            rows.append([
                v.vehicle_number, v.registration_number, v.bus_name,
                v.seating_capacity, v.allocated_count, v.available_seats,
                f"{v.occupancy_percentage}%", v.get_status_display()
            ])
        return _build_pdf_report("Fleet Seating & Occupancy Analytics", headers, rows, "transport_occupancy.pdf", is_landscape=True)


# ================================================================
# 7. ATTENDANCE REPORT
# ================================================================
class ExportAttendanceExcelView(LoginRequiredMixin, View):
    def get(self, request):
        if not _is_transport_authorized(request.user):
            raise PermissionDenied("Unauthorized.")
        wb = Workbook()
        ws = wb.active
        ws.title = "Attendance"
        headers = ["Date", "Trip", "Route", "Vehicle", "Roll No", "Student Name", "Boarding Stop", "Status", "Marked By"]
        _apply_excel_header_style(ws, headers)
        records = TransportAttendance.objects.all().select_related("student", "route", "vehicle", "boarding_stop", "marked_by").order_by("-date", "route__code")
        for att in records:
            ws.append([
                str(att.date), att.get_trip_type_display(), att.route.code, att.vehicle.vehicle_number,
                att.student.roll_no, att.student.name,
                att.boarding_stop.stop_name if att.boarding_stop else "-",
                att.get_status_display(), att.marked_by.username if att.marked_by else "-"
            ])
        _autofit_excel_columns(ws)
        resp = HttpResponse(content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        resp["Content-Disposition"] = 'attachment; filename="transport_attendance.xlsx"'
        wb.save(resp)
        return resp


class ExportAttendancePdfView(LoginRequiredMixin, View):
    def get(self, request):
        if not _is_transport_authorized(request.user):
            raise PermissionDenied("Unauthorized.")
        headers = ["Date", "Trip", "Route", "Bus", "Roll No", "Student Name", "Boarding Stop", "Status"]
        rows = []
        records = TransportAttendance.objects.all().select_related("student", "route", "vehicle", "boarding_stop").order_by("-date", "route__code")
        for att in records:
            rows.append([
                str(att.date), att.get_trip_type_display(), att.route.code, att.vehicle.vehicle_number,
                att.student.roll_no, att.student.name,
                att.boarding_stop.stop_name if att.boarding_stop else "-",
                att.get_status_display()
            ])
        return _build_pdf_report("Transport Daily Attendance Register", headers, rows, "transport_attendance.pdf", is_landscape=True)


# ================================================================
# 8. FEES REPORT
# ================================================================
class ExportFeesExcelView(LoginRequiredMixin, View):
    def get(self, request):
        if not _is_transport_authorized(request.user):
            raise PermissionDenied("Unauthorized.")
        wb = Workbook()
        ws = wb.active
        ws.title = "Fees"
        headers = ["Roll No", "Student Name", "Title", "Academic Year", "Billed (₹)", "Paid (₹)", "Outstanding (₹)", "Status", "Due Date"]
        _apply_excel_header_style(ws, headers)
        fees = FeeRecord.objects.filter(fee_type="TRANSPORT").select_related("student").order_by("-created_at")
        for f in fees:
            ws.append([
                f.student.roll_no, f.student.name, f.title, f.academic_year,
                float(f.amount), float(f.paid_amount), float(f.balance_amount),
                f.get_status_display(), str(f.due_date or "-")
            ])
        _autofit_excel_columns(ws)
        resp = HttpResponse(content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        resp["Content-Disposition"] = 'attachment; filename="transport_fees.xlsx"'
        wb.save(resp)
        return resp


class ExportFeesPdfView(LoginRequiredMixin, View):
    def get(self, request):
        if not _is_transport_authorized(request.user):
            raise PermissionDenied("Unauthorized.")
        headers = ["Roll No", "Student Name", "Title", "Year", "Billed (₹)", "Paid (₹)", "Balance (₹)", "Status"]
        rows = []
        fees = FeeRecord.objects.filter(fee_type="TRANSPORT").select_related("student").order_by("-created_at")
        for f in fees:
            rows.append([
                f.student.roll_no, f.student.name, f.title, f.academic_year,
                f"₹{f.amount}", f"₹{f.paid_amount}", f"₹{f.balance_amount}",
                f.get_status_display()
            ])
        return _build_pdf_report("Transport Fee Collection & Dues Register", headers, rows, "transport_fees.pdf", is_landscape=True)


# ================================================================
# 9. PASSES REPORT
# ================================================================
class ExportPassesExcelView(LoginRequiredMixin, View):
    def get(self, request):
        if not _is_transport_authorized(request.user):
            raise PermissionDenied("Unauthorized.")
        wb = Workbook()
        ws = wb.active
        ws.title = "Passes"
        headers = ["Pass No", "Roll No", "Student Name", "Route", "Stop", "Vehicle", "Issue Date", "Expiry Date", "Status"]
        _apply_excel_header_style(ws, headers)
        passes = TransportPass.objects.all().select_related("student", "allocation__route", "allocation__stop", "allocation__vehicle").order_by("-issue_date")
        for p in passes:
            ws.append([
                p.pass_number, p.student.roll_no, p.student.name,
                p.allocation.route.code, p.allocation.stop.stop_name, p.allocation.vehicle.vehicle_number,
                str(p.issue_date), str(p.expiry_date), p.get_status_display()
            ])
        _autofit_excel_columns(ws)
        resp = HttpResponse(content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        resp["Content-Disposition"] = 'attachment; filename="transport_passes.xlsx"'
        wb.save(resp)
        return resp


class ExportPassesPdfView(LoginRequiredMixin, View):
    def get(self, request):
        if not _is_transport_authorized(request.user):
            raise PermissionDenied("Unauthorized.")
        headers = ["Pass No", "Roll No", "Student Name", "Route", "Stop", "Bus No", "Issue Date", "Expiry Date", "Status"]
        rows = []
        passes = TransportPass.objects.all().select_related("student", "allocation__route", "allocation__stop", "allocation__vehicle").order_by("-issue_date")
        for p in passes:
            rows.append([
                p.pass_number, p.student.roll_no, p.student.name,
                p.allocation.route.code, p.allocation.stop.stop_name, p.allocation.vehicle.vehicle_number,
                str(p.issue_date), str(p.expiry_date), p.get_status_display()
            ])
        return _build_pdf_report("Transport Passes Issued Directory", headers, rows, "transport_passes.pdf", is_landscape=True)


# ================================================================
# 10. MAINTENANCE REPORT
# ================================================================
class ExportMaintenanceExcelView(LoginRequiredMixin, View):
    def get(self, request):
        if not _is_transport_authorized(request.user):
            raise PermissionDenied("Unauthorized.")
        wb = Workbook()
        ws = wb.active
        ws.title = "Maintenance"
        headers = ["Vehicle No", "Type", "Service Date", "Next Service", "Provider", "Cost (₹)", "Odometer", "Status", "Invoice No"]
        _apply_excel_header_style(ws, headers)
        for m in VehicleMaintenance.objects.all().select_related("vehicle").order_by("-service_date"):
            ws.append([
                m.vehicle.vehicle_number, m.get_maintenance_type_display(), str(m.service_date),
                str(m.next_service_date or "-"), m.service_provider, float(m.cost),
                m.odometer_reading or "-", m.get_status_display(), m.invoice_number or "-"
            ])
        _autofit_excel_columns(ws)
        resp = HttpResponse(content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        resp["Content-Disposition"] = 'attachment; filename="transport_maintenance.xlsx"'
        wb.save(resp)
        return resp


class ExportMaintenancePdfView(LoginRequiredMixin, View):
    def get(self, request):
        if not _is_transport_authorized(request.user):
            raise PermissionDenied("Unauthorized.")
        headers = ["Bus No", "Type", "Service Date", "Next Service", "Provider", "Cost (₹)", "Status"]
        rows = []
        for m in VehicleMaintenance.objects.all().select_related("vehicle").order_by("-service_date"):
            rows.append([
                m.vehicle.vehicle_number, m.get_maintenance_type_display(), str(m.service_date),
                str(m.next_service_date or "-"), m.service_provider, f"₹{m.cost}", m.get_status_display()
            ])
        return _build_pdf_report("Fleet Service & Maintenance Log", headers, rows, "transport_maintenance.pdf", is_landscape=True)


# ================================================================
# 11. COMPLAINTS REPORT
# ================================================================
class ExportComplaintsExcelView(LoginRequiredMixin, View):
    def get(self, request):
        if not _is_transport_authorized(request.user):
            raise PermissionDenied("Unauthorized.")
        wb = Workbook()
        ws = wb.active
        ws.title = "Complaints"
        headers = ["Complaint ID", "Roll No", "Student Name", "Category", "Title", "Priority", "Status", "Date", "Assigned Staff"]
        _apply_excel_header_style(ws, headers)
        for c in TransportComplaint.objects.all().select_related("student", "assigned_staff").order_by("-created_at"):
            ws.append([
                c.complaint_id, c.student.roll_no, c.student.name, c.get_category_display(),
                c.title, c.get_priority_display(), c.get_status_display(),
                c.created_at.strftime("%Y-%m-%d"), c.assigned_staff.username if c.assigned_staff else "-"
            ])
        _autofit_excel_columns(ws)
        resp = HttpResponse(content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        resp["Content-Disposition"] = 'attachment; filename="transport_complaints.xlsx"'
        wb.save(resp)
        return resp


class ExportComplaintsPdfView(LoginRequiredMixin, View):
    def get(self, request):
        if not _is_transport_authorized(request.user):
            raise PermissionDenied("Unauthorized.")
        headers = ["ID", "Roll No", "Student Name", "Category", "Title", "Priority", "Status", "Date"]
        rows = []
        for c in TransportComplaint.objects.all().select_related("student").order_by("-created_at"):
            rows.append([
                c.complaint_id, c.student.roll_no, c.student.name, c.get_category_display(),
                c.title, c.get_priority_display(), c.get_status_display(),
                c.created_at.strftime("%d-%m-%Y")
            ])
        return _build_pdf_report("Transport Grievance & Complaint Log", headers, rows, "transport_complaints.pdf", is_landscape=True)


# ================================================================
# 12. INCIDENTS REPORT
# ================================================================
class ExportIncidentsExcelView(LoginRequiredMixin, View):
    def get(self, request):
        if not _is_transport_authorized(request.user):
            raise PermissionDenied("Unauthorized.")
        wb = Workbook()
        ws = wb.active
        ws.title = "Incidents"
        headers = ["Incident ID", "Date", "Vehicle", "Route", "Severity", "Status", "Description", "Action Taken"]
        _apply_excel_header_style(ws, headers)
        for inc in TransportIncident.objects.all().select_related("vehicle", "route").order_by("-date"):
            ws.append([
                inc.incident_id, str(inc.date), inc.vehicle.vehicle_number,
                inc.route.code if inc.route else "-", inc.get_severity_display(),
                inc.get_status_display(), inc.description, inc.action_taken
            ])
        _autofit_excel_columns(ws)
        resp = HttpResponse(content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        resp["Content-Disposition"] = 'attachment; filename="transport_incidents.xlsx"'
        wb.save(resp)
        return resp


class ExportIncidentsPdfView(LoginRequiredMixin, View):
    def get(self, request):
        if not _is_transport_authorized(request.user):
            raise PermissionDenied("Unauthorized.")
        headers = ["ID", "Date", "Bus No", "Route", "Severity", "Status", "Description"]
        rows = []
        for inc in TransportIncident.objects.all().select_related("vehicle", "route").order_by("-date"):
            rows.append([
                inc.incident_id, str(inc.date), inc.vehicle.vehicle_number,
                inc.route.code if inc.route else "-", inc.get_severity_display(),
                inc.get_status_display(), inc.description[:60]
            ])
        return _build_pdf_report("Transport Incident & Safety Log", headers, rows, "transport_incidents.pdf", is_landscape=True)
