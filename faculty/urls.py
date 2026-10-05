from django.urls import path
from . import views


urlpatterns = [

    # ========================================================
    # FACULTY DASHBOARD
    # ========================================================

    path(
        "",
        views.dashboard,
        name="faculty_dashboard"
    ),


    # ========================================================
    # FACULTY PROFILE
    # ========================================================

    path(
        "leave-request/",
        views.leave_request,
        name="leave_request"
    ),

    path(
        "profile/",
        views.profile,
        name="faculty_profile"
    ),


    # ========================================================
    # ATTENDANCE
    # ========================================================

    path(
        "attendance/",
        views.mark_attendance,
        name="mark_attendance"
    ),

    path(
        "attendance-history/",
        views.attendance_history,
        name="attendance_history"
    ),


    # ========================================================
    # MARKS
    # ========================================================

    path(
        "marks/",
        views.marks_entry,
        name="marks_entry"
    ),

    path(
        "marks-history/",
        views.marks_history,
        name="marks_history"
    ),

    path(
        "marks/edit/<int:mark_id>/",
        views.edit_marks,
        name="edit_marks"
    ),

]
