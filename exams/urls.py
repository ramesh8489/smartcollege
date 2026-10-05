from django.urls import path
from . import views

urlpatterns = [
    # Exam session routes
    path("", views.exam_list, name="exam_list"),
    path("create/", views.exam_create, name="exam_create"),
    path("<int:pk>/", views.exam_detail, name="exam_detail"),
    path("<int:pk>/edit/", views.exam_edit, name="exam_edit"),
    path("<int:pk>/delete/", views.exam_delete, name="exam_delete"),
    path("<int:pk>/toggle-status/", views.toggle_exam_status, name="toggle_exam_status"),

    # Exam Schedule routes
    path("schedule/<int:schedule_id>/delete/", views.delete_schedule, name="delete_schedule"),
    path("schedule/<int:schedule_id>/marks/", views.exam_schedule_marks_entry, name="exam_schedule_marks_entry"),

    # Exam Marks & Assessment Management
    path("marks/", views.exam_marks_dashboard, name="exam_marks_dashboard"),
    path("marks/<int:mark_id>/edit/", views.exam_mark_edit, name="exam_mark_edit"),
    path("marks/<int:mark_id>/delete/", views.exam_mark_delete, name="exam_mark_delete"),

    # Student Results Portal
    path("my-results/", views.student_exam_results, name="student_exam_results"),
]
