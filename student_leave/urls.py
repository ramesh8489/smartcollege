from django.urls import path
from . import views

urlpatterns = [
    # Student views
    path("", views.leave_list, name="leave_list"),
    path("apply/", views.apply_leave, name="apply_leave"),
    path("<int:pk>/", views.leave_detail, name="leave_detail"),
    path("<int:pk>/cancel/", views.cancel_leave, name="cancel_leave"),
    path("<int:pk>/download/", views.download_document, name="download_leave_document"),

    # Approval workflows
    path("<int:pk>/faculty-action/", views.faculty_review_action, name="faculty_review_action"),
    path("<int:pk>/incharge-action/", views.incharge_review_action, name="incharge_review_action"),
    path("<int:pk>/admin-action/", views.admin_review_action, name="admin_review_action"),

    # Approver review dashboards
    path("faculty/", views.faculty_leave_list, name="faculty_leave_list"),
    path("incharge/", views.incharge_leave_list, name="incharge_leave_list"),
    path("admin-list/", views.admin_leave_list, name="admin_leave_list"),
]
