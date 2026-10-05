from decimal import Decimal
from django import forms
from django.utils import timezone
from students.models import Student
from fees.models import FeeRecord, FeePayment
from .models import (
    Vehicle,
    Route,
    Stop,
    Driver,
    Conductor,
    TransportApplication,
    TransportAllocation,
    TransportPass,
    TransportAttendance,
    VehicleMaintenance,
    TransportComplaint,
    TransportIncident,
)


class VehicleForm(forms.ModelForm):
    class Meta:
        model = Vehicle
        fields = [
            "vehicle_number",
            "registration_number",
            "vehicle_type",
            "bus_name",
            "seating_capacity",
            "status",
            "purchase_date",
            "insurance_expiry",
            "fitness_expiry",
            "pollution_expiry",
            "notes",
        ]
        widgets = {
            "vehicle_number": forms.TextInput(attrs={"class": "form-control", "placeholder": "e.g. BUS-01"}),
            "registration_number": forms.TextInput(attrs={"class": "form-control", "placeholder": "e.g. TN-01-AB-1234"}),
            "vehicle_type": forms.Select(attrs={"class": "form-control"}),
            "bus_name": forms.TextInput(attrs={"class": "form-control", "placeholder": "e.g. Central Campus Express"}),
            "seating_capacity": forms.NumberInput(attrs={"class": "form-control", "min": 1}),
            "status": forms.Select(attrs={"class": "form-control"}),
            "purchase_date": forms.DateInput(attrs={"class": "form-control", "type": "date"}),
            "insurance_expiry": forms.DateInput(attrs={"class": "form-control", "type": "date"}),
            "fitness_expiry": forms.DateInput(attrs={"class": "form-control", "type": "date"}),
            "pollution_expiry": forms.DateInput(attrs={"class": "form-control", "type": "date"}),
            "notes": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
        }


class RouteForm(forms.ModelForm):
    class Meta:
        model = Route
        fields = [
            "code",
            "name",
            "start_point",
            "destination",
            "assigned_vehicle",
            "is_active",
            "description",
        ]
        widgets = {
            "code": forms.TextInput(attrs={"class": "form-control", "placeholder": "e.g. RT-01"}),
            "name": forms.TextInput(attrs={"class": "form-control", "placeholder": "e.g. Route 1 - Tambaram to Campus"}),
            "start_point": forms.TextInput(attrs={"class": "form-control", "placeholder": "Starting Point"}),
            "destination": forms.TextInput(attrs={"class": "form-control", "placeholder": "Destination (Campus)"}),
            "assigned_vehicle": forms.Select(attrs={"class": "form-control"}),
            "is_active": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "description": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
        }


class StopForm(forms.ModelForm):
    class Meta:
        model = Stop
        fields = [
            "stop_name",
            "stop_code",
            "stop_order",
            "pickup_time",
            "drop_time",
            "distance_km",
            "fare_amount",
            "is_active",
        ]
        widgets = {
            "stop_name": forms.TextInput(attrs={"class": "form-control", "placeholder": "Stop Name"}),
            "stop_code": forms.TextInput(attrs={"class": "form-control", "placeholder": "Stop Code (optional)"}),
            "stop_order": forms.NumberInput(attrs={"class": "form-control", "min": 1}),
            "pickup_time": forms.TimeInput(attrs={"class": "form-control", "type": "time"}),
            "drop_time": forms.TimeInput(attrs={"class": "form-control", "type": "time"}),
            "distance_km": forms.NumberInput(attrs={"class": "form-control", "step": "0.1"}),
            "fare_amount": forms.NumberInput(attrs={"class": "form-control", "step": "0.01"}),
            "is_active": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }


class DriverForm(forms.ModelForm):
    class Meta:
        model = Driver
        fields = [
            "name",
            "employee_id",
            "phone",
            "email",
            "licence_number",
            "licence_expiry",
            "joining_date",
            "assigned_vehicle",
            "emergency_contact",
            "emergency_phone",
            "address",
            "is_active",
            "notes",
        ]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control"}),
            "employee_id": forms.TextInput(attrs={"class": "form-control", "placeholder": "e.g. DRV-101"}),
            "phone": forms.TextInput(attrs={"class": "form-control"}),
            "email": forms.EmailInput(attrs={"class": "form-control"}),
            "licence_number": forms.TextInput(attrs={"class": "form-control"}),
            "licence_expiry": forms.DateInput(attrs={"class": "form-control", "type": "date"}),
            "joining_date": forms.DateInput(attrs={"class": "form-control", "type": "date"}),
            "assigned_vehicle": forms.Select(attrs={"class": "form-control"}),
            "emergency_contact": forms.TextInput(attrs={"class": "form-control"}),
            "emergency_phone": forms.TextInput(attrs={"class": "form-control"}),
            "address": forms.Textarea(attrs={"class": "form-control", "rows": 2}),
            "is_active": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "notes": forms.Textarea(attrs={"class": "form-control", "rows": 2}),
        }


class ConductorForm(forms.ModelForm):
    class Meta:
        model = Conductor
        fields = [
            "name",
            "employee_id",
            "phone",
            "email",
            "joining_date",
            "assigned_vehicle",
            "assigned_route",
            "emergency_contact",
            "emergency_phone",
            "address",
            "is_active",
            "notes",
        ]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control"}),
            "employee_id": forms.TextInput(attrs={"class": "form-control", "placeholder": "e.g. CND-201"}),
            "phone": forms.TextInput(attrs={"class": "form-control"}),
            "email": forms.EmailInput(attrs={"class": "form-control"}),
            "joining_date": forms.DateInput(attrs={"class": "form-control", "type": "date"}),
            "assigned_vehicle": forms.Select(attrs={"class": "form-control"}),
            "assigned_route": forms.Select(attrs={"class": "form-control"}),
            "emergency_contact": forms.TextInput(attrs={"class": "form-control"}),
            "emergency_phone": forms.TextInput(attrs={"class": "form-control"}),
            "address": forms.Textarea(attrs={"class": "form-control", "rows": 2}),
            "is_active": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "notes": forms.Textarea(attrs={"class": "form-control", "rows": 2}),
        }


class TransportApplicationForm(forms.ModelForm):
    class Meta:
        model = TransportApplication
        fields = [
            "route",
            "stop",
            "academic_year",
            "requested_from_date",
            "parent_name",
            "parent_phone",
            "student_phone",
            "address",
            "remarks",
        ]
        widgets = {
            "route": forms.Select(attrs={"class": "form-control"}),
            "stop": forms.Select(attrs={"class": "form-control"}),
            "academic_year": forms.TextInput(attrs={"class": "form-control"}),
            "requested_from_date": forms.DateInput(attrs={"class": "form-control", "type": "date"}),
            "parent_name": forms.TextInput(attrs={"class": "form-control"}),
            "parent_phone": forms.TextInput(attrs={"class": "form-control"}),
            "student_phone": forms.TextInput(attrs={"class": "form-control"}),
            "address": forms.Textarea(attrs={"class": "form-control", "rows": 2}),
            "remarks": forms.Textarea(attrs={"class": "form-control", "rows": 2, "placeholder": "Any special pickup note or medical condition"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["route"].queryset = Route.objects.filter(is_active=True)
        self.fields["stop"].queryset = Stop.objects.filter(is_active=True).select_related("route")


class ApplicationReviewForm(forms.Form):
    ACTION_CHOICES = [
        ("APPROVED", "Approve Application"),
        ("REJECTED", "Reject Application"),
    ]
    action = forms.ChoiceField(choices=ACTION_CHOICES, widget=forms.Select(attrs={"class": "form-control"}))
    rejection_reason = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"class": "form-control", "rows": 3, "placeholder": "Mandatory if rejecting..."}),
    )
    remarks = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"class": "form-control", "rows": 2, "placeholder": "Approval remarks or internal notes"}),
    )

    def clean(self):
        cleaned_data = super().clean()
        action = cleaned_data.get("action")
        reason = cleaned_data.get("rejection_reason")
        if action == "REJECTED" and not reason:
            self.add_error("rejection_reason", "A specific reason is required when rejecting an application.")
        return cleaned_data


class TransportAllocationForm(forms.ModelForm):
    class Meta:
        model = TransportAllocation
        fields = [
            "student",
            "vehicle",
            "route",
            "stop",
            "academic_year",
            "pickup_time",
            "drop_time",
            "start_date",
            "end_date",
            "seat_number",
            "status",
            "remarks",
        ]
        widgets = {
            "student": forms.Select(attrs={"class": "form-control"}),
            "vehicle": forms.Select(attrs={"class": "form-control"}),
            "route": forms.Select(attrs={"class": "form-control"}),
            "stop": forms.Select(attrs={"class": "form-control"}),
            "academic_year": forms.TextInput(attrs={"class": "form-control"}),
            "pickup_time": forms.TimeInput(attrs={"class": "form-control", "type": "time"}),
            "drop_time": forms.TimeInput(attrs={"class": "form-control", "type": "time"}),
            "start_date": forms.DateInput(attrs={"class": "form-control", "type": "date"}),
            "end_date": forms.DateInput(attrs={"class": "form-control", "type": "date"}),
            "seat_number": forms.TextInput(attrs={"class": "form-control", "placeholder": "e.g. S-12"}),
            "status": forms.Select(attrs={"class": "form-control"}),
            "remarks": forms.Textarea(attrs={"class": "form-control", "rows": 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["student"].queryset = Student.objects.filter(is_active=True).order_by("name")
        self.fields["vehicle"].queryset = Vehicle.objects.filter(status="ACTIVE")
        self.fields["route"].queryset = Route.objects.filter(is_active=True)
        self.fields["stop"].queryset = Stop.objects.filter(is_active=True).select_related("route")


class TransportPassForm(forms.ModelForm):
    class Meta:
        model = TransportPass
        fields = [
            "academic_year",
            "issue_date",
            "expiry_date",
            "status",
        ]
        widgets = {
            "academic_year": forms.TextInput(attrs={"class": "form-control"}),
            "issue_date": forms.DateInput(attrs={"class": "form-control", "type": "date"}),
            "expiry_date": forms.DateInput(attrs={"class": "form-control", "type": "date"}),
            "status": forms.Select(attrs={"class": "form-control"}),
        }


class TransportAttendanceForm(forms.ModelForm):
    class Meta:
        model = TransportAttendance
        fields = [
            "date",
            "trip_type",
            "vehicle",
            "route",
            "student",
            "boarding_stop",
            "boarding_time",
            "status",
            "remarks",
        ]
        widgets = {
            "date": forms.DateInput(attrs={"class": "form-control", "type": "date"}),
            "trip_type": forms.Select(attrs={"class": "form-control"}),
            "vehicle": forms.Select(attrs={"class": "form-control"}),
            "route": forms.Select(attrs={"class": "form-control"}),
            "student": forms.Select(attrs={"class": "form-control"}),
            "boarding_stop": forms.Select(attrs={"class": "form-control"}),
            "boarding_time": forms.TimeInput(attrs={"class": "form-control", "type": "time"}),
            "status": forms.Select(attrs={"class": "form-control"}),
            "remarks": forms.TextInput(attrs={"class": "form-control"}),
        }


class VehicleMaintenanceForm(forms.ModelForm):
    class Meta:
        model = VehicleMaintenance
        fields = [
            "vehicle",
            "maintenance_type",
            "service_date",
            "next_service_date",
            "description",
            "service_provider",
            "cost",
            "odometer_reading",
            "invoice_number",
            "status",
            "remarks",
        ]
        widgets = {
            "vehicle": forms.Select(attrs={"class": "form-control"}),
            "maintenance_type": forms.Select(attrs={"class": "form-control"}),
            "service_date": forms.DateInput(attrs={"class": "form-control", "type": "date"}),
            "next_service_date": forms.DateInput(attrs={"class": "form-control", "type": "date"}),
            "description": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "service_provider": forms.TextInput(attrs={"class": "form-control", "placeholder": "Garage or Service Center"}),
            "cost": forms.NumberInput(attrs={"class": "form-control", "step": "0.01"}),
            "odometer_reading": forms.NumberInput(attrs={"class": "form-control"}),
            "invoice_number": forms.TextInput(attrs={"class": "form-control"}),
            "status": forms.Select(attrs={"class": "form-control"}),
            "remarks": forms.Textarea(attrs={"class": "form-control", "rows": 2}),
        }


class TransportComplaintForm(forms.ModelForm):
    class Meta:
        model = TransportComplaint
        fields = [
            "route",
            "vehicle",
            "category",
            "title",
            "description",
            "priority",
            "attachment",
        ]
        widgets = {
            "route": forms.Select(attrs={"class": "form-control"}),
            "vehicle": forms.Select(attrs={"class": "form-control"}),
            "category": forms.Select(attrs={"class": "form-control"}),
            "title": forms.TextInput(attrs={"class": "form-control", "placeholder": "Brief title of the issue"}),
            "description": forms.Textarea(attrs={"class": "form-control", "rows": 4, "placeholder": "Detailed description of the incident/issue..."}),
            "priority": forms.Select(attrs={"class": "form-control"}),
            "attachment": forms.FileInput(attrs={"class": "form-control"}),
        }


class AdminComplaintUpdateForm(forms.ModelForm):
    class Meta:
        model = TransportComplaint
        fields = [
            "assigned_staff",
            "status",
            "resolution",
        ]
        widgets = {
            "assigned_staff": forms.Select(attrs={"class": "form-control"}),
            "status": forms.Select(attrs={"class": "form-control"}),
            "resolution": forms.Textarea(attrs={"class": "form-control", "rows": 3, "placeholder": "Resolution details / remarks"}),
        }


class TransportIncidentForm(forms.ModelForm):
    class Meta:
        model = TransportIncident
        fields = [
            "date",
            "vehicle",
            "route",
            "severity",
            "status",
            "description",
            "action_taken",
        ]
        widgets = {
            "date": forms.DateInput(attrs={"class": "form-control", "type": "date"}),
            "vehicle": forms.Select(attrs={"class": "form-control"}),
            "route": forms.Select(attrs={"class": "form-control"}),
            "severity": forms.Select(attrs={"class": "form-control"}),
            "status": forms.Select(attrs={"class": "form-control"}),
            "description": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "action_taken": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
        }


# ================================================================
# FEES DEMAND & PAYMENT FORMS (REUSING FEES MODULE)
# ================================================================
class TransportFeeDemandForm(forms.Form):
    student = forms.ModelChoiceField(
        queryset=Student.objects.filter(is_active=True).order_by("name"),
        widget=forms.Select(attrs={"class": "form-control"})
    )
    title = forms.CharField(
        initial="Transport Fee - Annual",
        widget=forms.TextInput(attrs={"class": "form-control"})
    )
    academic_year = forms.CharField(
        initial="2026-27",
        widget=forms.TextInput(attrs={"class": "form-control"})
    )
    semester = forms.IntegerField(
        required=False,
        widget=forms.NumberInput(attrs={"class": "form-control", "placeholder": "Semester (optional)"})
    )
    amount = forms.DecimalField(
        max_digits=10,
        decimal_places=2,
        min_value=Decimal("1.00"),
        widget=forms.NumberInput(attrs={"class": "form-control", "step": "0.01"})
    )
    due_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={"class": "form-control", "type": "date"})
    )
    remarks = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"class": "form-control", "rows": 2})
    )


class TransportFeePaymentForm(forms.Form):
    amount = forms.DecimalField(
        max_digits=10,
        decimal_places=2,
        min_value=Decimal("0.01"),
        widget=forms.NumberInput(attrs={"class": "form-control", "step": "0.01"})
    )
    payment_mode = forms.ChoiceField(
        choices=FeePayment.PAYMENT_MODE_CHOICES,
        widget=forms.Select(attrs={"class": "form-control"})
    )
    payment_date = forms.DateField(
        initial=timezone.now,
        widget=forms.DateInput(attrs={"class": "form-control", "type": "date"})
    )
    reference_number = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "UPI ref, Cheque or Txn ID"})
    )
    remarks = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"class": "form-control", "rows": 2})
    )
