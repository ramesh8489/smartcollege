from django.urls import path
from . import views


urlpatterns = [

    # Student Dashboard
    path(
        "",
        views.dashboard,
        name="dashboard"
    ),

    # Student Profile
    path(
        "profile/",
        views.profile,
        name="profile"
    ),

    # Attendance History
    path(
        "attendance-history/",
        views.attendance_history,
        name="attendance_history"
    ),

    # Marks History
    path(
        "marks-history/",
        views.marks_history,
        name="marks_history"
    ),

]
