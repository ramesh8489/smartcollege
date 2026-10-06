from django.urls import path

from . import views


urlpatterns = [
    path("", views.fee_dashboard, name="fee_dashboard"),
    path("pay/<int:record_id>/", views.pay_fee, name="pay_fee"),
    path("receipt/<int:payment_id>/", views.payment_receipt, name="payment_receipt"),
]
