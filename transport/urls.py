from django.urls import path
from . import views
from . import reports

app_name = "transport"

urlpatterns = [
    # Entry
    path("", views.TransportHomeView.as_view(), name="home"),
    path("portal/", views.StudentTransportPortalView.as_view(), name="student_portal"),
    path("dashboard/", views.TransportAdminDashboardView.as_view(), name="admin_dashboard"),

    # Student Applications
    path("applications/", views.StudentTransportApplicationListView.as_view(), name="application_list"),
    path("applications/apply/", views.StudentTransportApplicationCreateView.as_view(), name="application_apply"),
    path("apply/", views.StudentTransportApplicationCreateView.as_view(), name="student_apply"),
    path("applications/<int:pk>/", views.StudentTransportApplicationDetailView.as_view(), name="application_detail"),

    # Student Pass, Attendance, Fees, Complaints
    path("pass/", views.StudentTransportPassView.as_view(), name="student_pass"),
    path("pass/pdf/", views.StudentTransportPassPdfView.as_view(), name="student_pass_pdf"),
    path("attendance/", views.StudentTransportAttendanceView.as_view(), name="student_attendance"),
    path("fees/", views.StudentTransportFeesView.as_view(), name="student_fees"),
    path("complaints/", views.StudentTransportComplaintListView.as_view(), name="student_complaints"),
    path("complaints/create/", views.StudentTransportComplaintCreateView.as_view(), name="student_complaint_create"),
    path("complaints/<int:pk>/", views.StudentTransportComplaintDetailView.as_view(), name="student_complaint_detail"),

    # Admin: Vehicles
    path("admin/vehicles/", views.AdminVehicleListView.as_view(), name="admin_vehicles"),
    path("admin/vehicles/create/", views.AdminVehicleCreateView.as_view(), name="admin_vehicle_create"),
    path("admin/vehicles/<int:pk>/", views.AdminVehicleDetailView.as_view(), name="admin_vehicle_detail"),
    path("admin/vehicles/<int:pk>/edit/", views.AdminVehicleUpdateView.as_view(), name="admin_vehicle_update"),

    # Admin: Routes & Stops
    path("admin/routes/", views.AdminRouteListView.as_view(), name="admin_routes"),
    path("admin/routes/create/", views.AdminRouteCreateView.as_view(), name="admin_route_create"),
    path("admin/routes/<int:pk>/", views.AdminRouteDetailView.as_view(), name="admin_route_detail"),
    path("admin/routes/<int:pk>/edit/", views.AdminRouteUpdateView.as_view(), name="admin_route_update"),
    path("admin/routes/<int:route_id>/stops/create/", views.AdminStopCreateView.as_view(), name="admin_stop_create"),
    path("admin/stops/<int:pk>/edit/", views.AdminStopUpdateView.as_view(), name="admin_stop_update"),
    path("admin/stops/<int:pk>/delete/", views.AdminStopDeleteView.as_view(), name="admin_stop_delete"),

    # Admin: Drivers & Conductors
    path("admin/drivers/", views.AdminDriverListView.as_view(), name="admin_drivers"),
    path("admin/drivers/create/", views.AdminDriverCreateView.as_view(), name="admin_driver_create"),
    path("admin/drivers/<int:pk>/edit/", views.AdminDriverUpdateView.as_view(), name="admin_driver_update"),
    path("admin/conductors/", views.AdminConductorListView.as_view(), name="admin_conductors"),
    path("admin/conductors/create/", views.AdminConductorCreateView.as_view(), name="admin_conductor_create"),
    path("admin/conductors/<int:pk>/edit/", views.AdminConductorUpdateView.as_view(), name="admin_conductor_update"),

    # Admin: Applications
    path("admin/applications/", views.AdminApplicationListView.as_view(), name="admin_applications"),
    path("admin/applications/<int:pk>/review/", views.AdminApplicationReviewView.as_view(), name="admin_application_review"),

    # Admin: Allocations
    path("admin/allocations/", views.AdminAllocationListView.as_view(), name="admin_allocations"),
    path("admin/allocations/create/", views.AdminAllocationCreateView.as_view(), name="admin_allocation_create"),
    path("admin/allocations/<int:pk>/", views.AdminAllocationDetailView.as_view(), name="admin_allocation_detail"),
    path("admin/allocations/<int:pk>/cancel/", views.AdminAllocationCancelView.as_view(), name="admin_allocation_cancel"),

    # Admin: Passes
    path("admin/passes/", views.AdminPassListView.as_view(), name="admin_passes"),
    path("admin/passes/<int:pk>/", views.AdminPassDetailView.as_view(), name="admin_pass_detail"),
    path("admin/passes/<int:pk>/pdf/", views.AdminPassPdfDownloadView.as_view(), name="admin_pass_pdf"),

    # Admin: Attendance
    path("admin/attendance/", views.AdminAttendanceView.as_view(), name="admin_attendance"),
    path("admin/attendance/mark/", views.AdminMarkAttendanceView.as_view(), name="admin_attendance_mark"),

    # Admin: Maintenance
    path("admin/maintenance/", views.AdminMaintenanceListView.as_view(), name="admin_maintenance"),
    path("admin/maintenance/create/", views.AdminMaintenanceCreateView.as_view(), name="admin_maintenance_create"),
    path("admin/maintenance/<int:pk>/edit/", views.AdminMaintenanceUpdateView.as_view(), name="admin_maintenance_update"),

    # Admin: Complaints & Incidents
    path("admin/complaints/", views.AdminComplaintListView.as_view(), name="admin_complaints"),
    path("admin/complaints/<int:pk>/", views.AdminComplaintDetailView.as_view(), name="admin_complaint_detail"),
    path("admin/incidents/", views.AdminIncidentListView.as_view(), name="admin_incidents"),
    path("admin/incidents/create/", views.AdminIncidentCreateView.as_view(), name="admin_incident_create"),

    # Admin: Fees
    path("admin/fees/", views.AdminTransportFeeListView.as_view(), name="admin_fees"),
    path("admin/fees/create/", views.AdminCreateTransportFeeView.as_view(), name="admin_fee_create"),
    path("admin/fees/<int:fee_id>/pay/", views.AdminRecordTransportPaymentView.as_view(), name="admin_fee_pay"),

    # Reports & Exports
    path("admin/reports/", reports.TransportReportsHubView.as_view(), name="admin_reports_hub"),
    path("admin/reports/vehicles/excel/", reports.ExportVehicleExcelView.as_view(), name="export_vehicles_excel"),
    path("admin/reports/vehicles/pdf/", reports.ExportVehiclePdfView.as_view(), name="export_vehicles_pdf"),
    path("admin/reports/routes/excel/", reports.ExportRouteExcelView.as_view(), name="export_routes_excel"),
    path("admin/reports/routes/pdf/", reports.ExportRoutePdfView.as_view(), name="export_routes_pdf"),
    path("admin/reports/stops/excel/", reports.ExportStopExcelView.as_view(), name="export_stops_excel"),
    path("admin/reports/stops/pdf/", reports.ExportStopPdfView.as_view(), name="export_stops_pdf"),
    path("admin/reports/drivers/excel/", reports.ExportDriverExcelView.as_view(), name="export_drivers_excel"),
    path("admin/reports/drivers/pdf/", reports.ExportDriverPdfView.as_view(), name="export_drivers_pdf"),
    path("admin/reports/allocations/excel/", reports.ExportAllocationExcelView.as_view(), name="export_allocations_excel"),
    path("admin/reports/allocations/pdf/", reports.ExportAllocationPdfView.as_view(), name="export_allocations_pdf"),
    path("admin/reports/occupancy/excel/", reports.ExportOccupancyExcelView.as_view(), name="export_occupancy_excel"),
    path("admin/reports/occupancy/pdf/", reports.ExportOccupancyPdfView.as_view(), name="export_occupancy_pdf"),
    path("admin/reports/attendance/excel/", reports.ExportAttendanceExcelView.as_view(), name="export_attendance_excel"),
    path("admin/reports/attendance/pdf/", reports.ExportAttendancePdfView.as_view(), name="export_attendance_pdf"),
    path("admin/reports/fees/excel/", reports.ExportFeesExcelView.as_view(), name="export_fees_excel"),
    path("admin/reports/fees/pdf/", reports.ExportFeesPdfView.as_view(), name="export_fees_pdf"),
    path("admin/reports/passes/excel/", reports.ExportPassesExcelView.as_view(), name="export_passes_excel"),
    path("admin/reports/passes/pdf/", reports.ExportPassesPdfView.as_view(), name="export_passes_pdf"),
    path("admin/reports/maintenance/excel/", reports.ExportMaintenanceExcelView.as_view(), name="export_maintenance_excel"),
    path("admin/reports/maintenance/pdf/", reports.ExportMaintenancePdfView.as_view(), name="export_maintenance_pdf"),
    path("admin/reports/complaints/excel/", reports.ExportComplaintsExcelView.as_view(), name="export_complaints_excel"),
    path("admin/reports/complaints/pdf/", reports.ExportComplaintsPdfView.as_view(), name="export_complaints_pdf"),
    path("admin/reports/incidents/excel/", reports.ExportIncidentsExcelView.as_view(), name="export_incidents_excel"),
    path("admin/reports/incidents/pdf/", reports.ExportIncidentsPdfView.as_view(), name="export_incidents_pdf"),
]
