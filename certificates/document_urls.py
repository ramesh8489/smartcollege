from django.urls import path
from . import views

urlpatterns = [
    # Student Documents Portal
    path("", views.student_documents_portal, name="student_documents_portal"),

    # Admin Document Management & Verification
    path("admin/", views.admin_document_management, name="admin_document_management"),
    path("verify/<int:pk>/", views.admin_document_verify, name="admin_document_verify"),

    # Secure Download
    path("download/<int:pk>/", views.download_student_document, name="download_student_document"),
    path("detail/<int:pk>/", views.download_student_document, name="document_detail"),
]
