from django.urls import path
from . import views


urlpatterns = [

    path(
        "incharge/",
        views.incharge_dashboard,
        name="incharge_dashboard"
    ),

    path(
        "incharge/delete-slot/<int:slot_id>/",
        views.delete_slot,
        name="delete_slot"
    ),

    path(
        "incharge-leaves/",
        views.incharge_leaves,
        name="incharge_leaves"
    ),

    path(
        "my-timetable/",
        views.my_timetable,
        name="my_timetable"
    ),

    path(
        "post-circular/",
        views.post_circular,
        name="post_circular"
    ),

    path(
        "delete-circular/<int:circular_id>/",
        views.delete_circular,
        name="delete_circular"
    ),

    path(
        "circulars/",
        views.circular_list,
        name="circular_list"
    ),

    path(
        "notifications/",
        views.notifications,
        name="notifications"
    ),

]
