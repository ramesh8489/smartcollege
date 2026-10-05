from django.urls import path
from . import views

urlpatterns = [
    # Assignment core routes
    path("", views.assignment_list, name="assignment_list"),
    path("create/", views.assignment_create, name="assignment_create"),
    path("<int:pk>/", views.assignment_detail, name="assignment_detail"),
    path("<int:pk>/edit/", views.assignment_edit, name="assignment_edit"),
    path("<int:pk>/delete/", views.assignment_delete, name="assignment_delete"),
    path("<int:pk>/download-material/", views.download_material, name="download_assignment_material"),

    # Submission evaluation & download routes
    path("submission/<int:submission_id>/evaluate/", views.evaluate_submission, name="evaluate_submission"),
    path("submission/<int:submission_id>/download/", views.download_submission, name="download_submission"),

    # Student portal my submissions
    path("my-submissions/", views.student_submissions_list, name="student_submissions_list"),
]
