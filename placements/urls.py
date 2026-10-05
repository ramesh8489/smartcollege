from django.urls import path
from . import views

urlpatterns = [
    # Dashboard
    path("", views.dashboard, name="placements_dashboard"),

    # Company Management
    path("companies/", views.company_list, name="company_list"),
    path("companies/add/", views.company_create, name="company_create"),
    path("companies/<int:pk>/", views.company_detail, name="company_detail"),
    path("companies/<int:pk>/edit/", views.company_edit, name="company_edit"),
    path("companies/<int:pk>/delete/", views.company_delete, name="company_delete"),

    # Placement Drives
    path("drives/", views.drive_list, name="drive_list"),
    path("drives/create/", views.drive_create, name="drive_create"),
    path("drives/<int:pk>/", views.drive_detail, name="drive_detail"),
    path("drives/<int:pk>/edit/", views.drive_edit, name="drive_edit"),
    path("drives/<int:pk>/apply/", views.student_apply_drive, name="student_apply_drive"),

    # Applications & Rounds
    path("applications/", views.application_list, name="application_list"),
    path("applications/<int:pk>/", views.application_detail, name="application_detail"),
    path("applications/<int:pk>/status/", views.application_status_update, name="application_status_update"),
    path("applications/<int:application_id>/schedule-round/", views.round_create, name="round_create"),
    path("applications/rounds/<int:pk>/edit/", views.round_update, name="round_update"),
    path("applications/<int:application_id>/record-result/", views.result_create, name="result_create"),
    path("applications/<int:pk>/resume/", views.download_resume, name="download_resume"),
    path("results/<int:pk>/offer/", views.download_offer_letter, name="download_offer_letter"),

    # Student Portal & History
    path("student/", views.student_portal, name="student_placement_portal"),
    path("student/history/", views.student_history, name="student_placement_history"),
    path("student/profile/", views.student_profile_edit, name="student_placement_profile"),
]
