from django.urls import path
from . import views


urlpatterns = [

    # ========================================================
    # LOGIN
    # ========================================================

    path(
        "login/",
        views.login_view,
        name="login"
    ),


    # ========================================================
    # REGISTER
    # ========================================================

    path(
        "register/",
        views.register_view,
        name="register"
    ),


    # ========================================================
    # LOGOUT
    # ========================================================

    path(
        "logout/",
        views.logout_view,
        name="logout"
    ),


    # ========================================================
    # ADMIN DASHBOARD
    # ========================================================

    path(
        "admin-dashboard/",
        views.admin_dashboard,
        name="admin_dashboard"
    ),


    # ========================================================
    # APPROVE / REJECT
    # ========================================================

    path(
        "leave-messages/seen/<int:leave_id>/",
        views.mark_leave_seen,
        name="mark_leave_seen"
    ),

    path(
        "approve-student/<int:student_id>/",
        views.approve_student,
        name="approve_student"
    ),

    path(
        "reject-student/<int:student_id>/",
        views.reject_student,
        name="reject_student"
    ),

    path(
        "approve-faculty/<int:faculty_id>/",
        views.approve_faculty,
        name="approve_faculty"
    ),

    path(
        "reject-faculty/<int:faculty_id>/",
        views.reject_faculty,
        name="reject_faculty"
    ),

]
