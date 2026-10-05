from django.urls import path
from . import views

urlpatterns = [
    # Student Certificate Portal
    path("", views.student_portal, name="certificates_student_portal"),
    path("request/", views.certificate_request_create, name="certificate_request_create"),
    path("history/", views.student_certificate_history, name="student_certificate_history"),

    # Request Detail & Workflow Actions
    path("detail/<int:pk>/", views.certificate_request_detail, name="certificate_request_detail"),
    path("detail/<int:pk>/action/", views.certificate_request_action, name="certificate_request_action"),
    path("download/<int:pk>/", views.download_certificate_pdf, name="download_certificate_pdf"),

    # Public Verification
    path("verify/", views.certificate_verify, name="certificate_verify_search"),
    path("verify/<str:certificate_number>/", views.certificate_verify, name="certificate_verify"),

    # Admin Management
    path("admin/", views.admin_dashboard, name="certificates_admin_dashboard"),
    path("admin/requests/", views.admin_dashboard, name="certificates_admin_requests"),
    path("admin/types/", views.certificate_type_list, name="certificate_type_list"),
    path("admin/types/add/", views.certificate_type_create, name="certificate_type_create"),
    path("admin/types/<int:pk>/edit/", views.certificate_type_edit, name="certificate_type_edit"),
    path("admin/types/<int:pk>/toggle/", views.certificate_type_toggle, name="certificate_type_toggle"),
]
