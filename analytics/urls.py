from django.urls import path
from . import views

app_name = "analytics"

urlpatterns = [
    path("", views.dashboard_view, name="dashboard"),
    path("academic/", views.academic_analytics_view, name="academic"),
    path("attendance/", views.attendance_analytics_view, name="attendance"),
    path("risk/", views.risk_students_view, name="risk"),
    path("fees/", views.fees_analytics_view, name="fees"),
    path("library/", views.library_analytics_view, name="library"),
    path("placements/", views.placement_analytics_view, name="placements"),
    path("certificates/", views.certificate_analytics_view, name="certificates"),
    path("faculty/", views.faculty_analytics_view, name="faculty"),
    path("my/", views.student_analytics_view, name="my"),
    path("student/<int:student_id>/", views.student_analytics_view, name="student_detail"),
    path("export/excel/", views.export_excel_view, name="export_excel"),
    path("export/pdf/", views.export_pdf_view, name="export_pdf"),
]
