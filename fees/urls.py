from django.urls import path

from . import views


urlpatterns = [
    path("", views.fee_dashboard, name="fee_dashboard"),
    path("receipt/<int:payment_id>/", views.payment_receipt, name="payment_receipt"),
]
