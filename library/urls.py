from django.urls import path
from . import views

urlpatterns = [
    path("", views.dashboard, name="library_dashboard"),
    path("issue/", views.issue_book, name="library_issue"),
    path("return/<int:loan_id>/", views.return_book, name="library_return"),
]
