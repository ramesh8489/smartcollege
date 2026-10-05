from django import forms
from fees.models import FeePayment, FeeRecord
from .models import (
    HostelApplication,
    Hostel,
    HostelRoom,
    HostelAllocation,
    HostelBed,
    HostelCheckInOut,
    HostelRoomTransfer,
    HostelComplaint,
    HostelNotice,
    HostelWarden,
    HostelVisitor,
)


class HostelApplicationForm(forms.ModelForm):
    class Meta:
        model = HostelApplication
        fields = [
            "hostel_preference",
            "room_type_preference",
            "academic_year",
            "reason",
            "remarks",
        ]
        widgets = {
            "hostel_preference": forms.Select(attrs={"class": "form-control"}),
            "room_type_preference": forms.Select(attrs={"class": "form-control"}),
            "academic_year": forms.TextInput(attrs={"class": "form-control", "placeholder": "2026-27"}),
            "reason": forms.Textarea(attrs={"class": "form-control", "rows": 3, "placeholder": "Explain why you require hostel accommodation..."}),
            "remarks": forms.Textarea(attrs={"class": "form-control", "rows": 2, "placeholder": "Any special requirements or dietary/accessibility needs..."}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["hostel_preference"].queryset = Hostel.objects.filter(is_active=True)


class ApplicationReviewForm(forms.Form):
    ACTION_CHOICES = [
        ("APPROVED", "Approve Application"),
        ("REJECTED", "Reject Application"),
        ("WAITLISTED", "Place on Waitlist"),
    ]

    action = forms.ChoiceField(
        choices=ACTION_CHOICES,
        widget=forms.Select(attrs={"class": "form-control"}),
    )
    remarks = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"class": "form-control", "rows": 2, "placeholder": "Administrative review remarks..."}),
    )
    rejection_reason = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"class": "form-control", "rows": 3, "placeholder": "Mandatory reason if rejecting..."}),
    )

    def clean(self):
        cleaned_data = super().clean()
        action = cleaned_data.get("action")
        rejection_reason = cleaned_data.get("rejection_reason")
        if action == "REJECTED" and not rejection_reason:
            self.add_error("rejection_reason", "A specific rejection reason is strictly required when rejecting an application.")
        return cleaned_data


class HostelAllocationForm(forms.ModelForm):
    class Meta:
        model = HostelAllocation
        fields = [
            "student",
            "hostel",
            "room",
            "bed",
            "academic_year",
            "allocation_date",
            "expected_checkout_date",
            "remarks",
        ]
        widgets = {
            "student": forms.Select(attrs={"class": "form-control"}),
            "hostel": forms.Select(attrs={"class": "form-control"}),
            "room": forms.Select(attrs={"class": "form-control"}),
            "bed": forms.Select(attrs={"class": "form-control"}),
            "academic_year": forms.TextInput(attrs={"class": "form-control", "placeholder": "2026-27"}),
            "allocation_date": forms.DateInput(attrs={"class": "form-control", "type": "date"}),
            "expected_checkout_date": forms.DateInput(attrs={"class": "form-control", "type": "date"}),
            "remarks": forms.Textarea(attrs={"class": "form-control", "rows": 2, "placeholder": "Key deposit, condition of mattress, etc."}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from students.models import Student

        # Exclude students who already have an active allocation
        active_student_ids = HostelAllocation.objects.filter(status="ACTIVE").values_list("student_id", flat=True)
        self.fields["student"].queryset = Student.objects.filter(is_active=True).exclude(id__in=active_student_ids)

        self.fields["hostel"].queryset = Hostel.objects.filter(is_active=True)
        self.fields["room"].queryset = HostelRoom.objects.filter(is_active=True).exclude(status__in=["FULL", "MAINTENANCE", "INACTIVE"])
        self.fields["bed"].queryset = HostelBed.objects.filter(is_active=True, status="AVAILABLE")

    def clean(self):
        cleaned_data = super().clean()
        bed = cleaned_data.get("bed")
        room = cleaned_data.get("room")
        hostel = cleaned_data.get("hostel")

        if bed and room and bed.room_id != room.id:
            self.add_error("bed", f"Bed '{bed.bed_number}' does not belong to Room '{room.room_number}'.")
        if room and hostel and room.hostel_id != hostel.id:
            self.add_error("room", f"Room '{room.room_number}' does not belong to Hostel '{hostel.name}'.")

        return cleaned_data


class CheckInOutForm(forms.ModelForm):
    class Meta:
        model = HostelCheckInOut
        fields = ["event_type", "event_date", "reason", "remarks"]
        widgets = {
            "event_type": forms.Select(attrs={"class": "form-control"}),
            "event_date": forms.DateInput(attrs={"class": "form-control", "type": "date"}),
            "reason": forms.Textarea(attrs={"class": "form-control", "rows": 2, "placeholder": "Reason for checkout / checkin observations..."}),
            "remarks": forms.Textarea(attrs={"class": "form-control", "rows": 2, "placeholder": "Condition of inventory, keys returned, etc."}),
        }

    def clean(self):
        cleaned_data = super().clean()
        event_type = cleaned_data.get("event_type")
        reason = cleaned_data.get("reason")
        if event_type == "CHECK_OUT" and not reason:
            self.add_error("reason", "A specific reason is required when processing a student checkout.")
        return cleaned_data


class HostelRoomTransferForm(forms.Form):
    new_hostel = forms.ModelChoiceField(
        queryset=Hostel.objects.filter(is_active=True),
        widget=forms.Select(attrs={"class": "form-control"}),
        label="Destination Hostel",
    )
    new_room = forms.ModelChoiceField(
        queryset=HostelRoom.objects.filter(is_active=True).exclude(status__in=["FULL", "MAINTENANCE", "INACTIVE"]),
        widget=forms.Select(attrs={"class": "form-control"}),
        label="Destination Room",
    )
    new_bed = forms.ModelChoiceField(
        queryset=HostelBed.objects.filter(is_active=True, status="AVAILABLE"),
        widget=forms.Select(attrs={"class": "form-control"}),
        label="Destination Bed (Available)",
    )
    transfer_date = forms.DateField(
        widget=forms.DateInput(attrs={"class": "form-control", "type": "date"}),
        label="Effective Transfer Date",
    )
    reason = forms.CharField(
        widget=forms.Textarea(attrs={"class": "form-control", "rows": 2, "placeholder": "Reason for room transfer (e.g. medical need, mutual swap, maintenance)..."}),
        label="Transfer Reason",
    )
    remarks = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"class": "form-control", "rows": 2, "placeholder": "Key exchange remarks, luggage notes..."}),
        label="Administrative Remarks",
    )

    def clean(self):
        cleaned_data = super().clean()
        new_bed = cleaned_data.get("new_bed")
        new_room = cleaned_data.get("new_room")
        new_hostel = cleaned_data.get("new_hostel")

        if new_bed and new_room and new_bed.room_id != new_room.id:
            self.add_error("new_bed", f"Bed '{new_bed.bed_number}' does not belong to Room '{new_room.room_number}'.")
        if new_room and new_hostel and new_room.hostel_id != new_hostel.id:
            self.add_error("new_room", f"Room '{new_room.room_number}' does not belong to Hostel '{new_hostel.name}'.")

        return cleaned_data


class HostelFeeDemandForm(forms.Form):
    student = forms.ModelChoiceField(
        queryset=None,
        widget=forms.Select(attrs={"class": "form-control"}),
        label="Student Resident",
    )
    fee_subtype = forms.ChoiceField(
        choices=[
            ("Hostel Admission Fee", "Hostel Admission Fee"),
            ("Hostel Rent", "Hostel Rent"),
            ("Mess Fee", "Mess Fee"),
            ("Maintenance Fee", "Maintenance Fee"),
            ("Security Deposit", "Security Deposit"),
            ("Other Hostel Fee", "Other Hostel Fee"),
        ],
        widget=forms.Select(attrs={"class": "form-control"}),
        label="Hostel Fee Category",
    )
    amount = forms.DecimalField(
        max_digits=10,
        decimal_places=2,
        widget=forms.NumberInput(attrs={"class": "form-control", "placeholder": "5000.00"}),
        label="Fee Amount (₹)",
    )
    academic_year = forms.CharField(
        initial="2026-27",
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "2026-27"}),
        label="Academic Session",
    )
    due_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={"class": "form-control", "type": "date"}),
        label="Payment Due Date",
    )
    remarks = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"class": "form-control", "rows": 2, "placeholder": "Notes (e.g. Term 1 Mess charge, Security deposit refund terms)..."}),
        label="Remarks",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from students.models import Student
        self.fields["student"].queryset = Student.objects.filter(is_active=True).order_by("name")


class HostelFeePaymentForm(forms.ModelForm):
    class Meta:
        model = FeePayment
        fields = ["amount", "payment_date", "payment_mode", "reference_number", "remarks"]
        widgets = {
            "amount": forms.NumberInput(attrs={"class": "form-control", "step": "0.01"}),
            "payment_date": forms.DateInput(attrs={"class": "form-control", "type": "date"}),
            "payment_mode": forms.Select(attrs={"class": "form-control"}),
            "reference_number": forms.TextInput(attrs={"class": "form-control", "placeholder": "Transaction / Cheque / UTR No."}),
            "remarks": forms.Textarea(attrs={"class": "form-control", "rows": 2, "placeholder": "Payment transaction notes..."}),
        }


class StudentComplaintForm(forms.ModelForm):
    class Meta:
        model = HostelComplaint
        fields = ["category", "title", "description", "priority", "attachment"]
        widgets = {
            "category": forms.Select(attrs={"class": "form-control"}),
            "title": forms.TextInput(attrs={"class": "form-control", "placeholder": "Brief issue summary (e.g. Geyser not heating, Fan regulator broken)..."}),
            "description": forms.Textarea(attrs={"class": "form-control", "rows": 4, "placeholder": "Provide detailed description of the maintenance issue..."}),
            "priority": forms.Select(attrs={"class": "form-control"}),
            "attachment": forms.FileInput(attrs={"class": "form-control"}),
        }


class AdminComplaintUpdateForm(forms.ModelForm):
    class Meta:
        model = HostelComplaint
        fields = ["status", "assigned_staff", "priority", "resolution"]
        widgets = {
            "status": forms.Select(attrs={"class": "form-control"}),
            "assigned_staff": forms.Select(attrs={"class": "form-control"}),
            "priority": forms.Select(attrs={"class": "form-control"}),
            "resolution": forms.Textarea(attrs={"class": "form-control", "rows": 3, "placeholder": "Details of repair, resolution summary, or reason for rejection..."}),
        }

    def clean(self):
        cleaned_data = super().clean()
        status = cleaned_data.get("status")
        resolution = cleaned_data.get("resolution")

        if status in ["RESOLVED", "CLOSED", "REJECTED"]:
            if not resolution or not resolution.strip():
                self.add_error("resolution", "A resolution summary or explanation is required when resolving, closing, or rejecting a complaint.")

        return cleaned_data


class HostelNoticeForm(forms.ModelForm):
    class Meta:
        model = HostelNotice
        fields = [
            "hostel",
            "title",
            "message",
            "publish_date",
            "expiry_date",
            "priority",
            "attachment",
        ]
        widgets = {
            "hostel": forms.Select(attrs={"class": "form-control"}),
            "title": forms.TextInput(attrs={"class": "form-control", "placeholder": "Notice Headline / Circular Title..."}),
            "message": forms.Textarea(attrs={"class": "form-control", "rows": 4, "placeholder": "Enter detailed circular or notice announcement..."}),
            "publish_date": forms.DateInput(attrs={"class": "form-control", "type": "date"}),
            "expiry_date": forms.DateInput(attrs={"class": "form-control", "type": "date"}),
            "priority": forms.Select(attrs={"class": "form-control"}),
            "attachment": forms.FileInput(attrs={"class": "form-control"}),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        if user and not user.is_superuser:
            from .views import get_user_assigned_hostel_ids
            assigned_ids = get_user_assigned_hostel_ids(user)
            self.fields["hostel"].queryset = Hostel.objects.filter(id__in=assigned_ids, is_active=True)


class StudentVisitorRequestForm(forms.ModelForm):
    class Meta:
        model = HostelVisitor
        fields = [
            "visitor_name",
            "relationship",
            "phone",
            "visit_date",
            "purpose",
            "remarks",
        ]
        widgets = {
            "visitor_name": forms.TextInput(attrs={"class": "form-control", "placeholder": "Full name of visitor"}),
            "relationship": forms.TextInput(attrs={"class": "form-control", "placeholder": "Relationship (Parent, Guardian, Sibling, Friend)"}),
            "phone": forms.TextInput(attrs={"class": "form-control", "placeholder": "Contact phone number"}),
            "visit_date": forms.DateInput(attrs={"class": "form-control", "type": "date"}),
            "purpose": forms.TextInput(attrs={"class": "form-control", "placeholder": "Purpose of visit..."}),
            "remarks": forms.Textarea(attrs={"class": "form-control", "rows": 2, "placeholder": "Special notes or expected arrival time..."}),
        }

    def clean_phone(self):
        phone = self.cleaned_data.get("phone", "").strip()
        if not phone:
            raise forms.ValidationError("Visitor phone number is required.")
        return phone


class AdminVisitorUpdateForm(forms.ModelForm):
    class Meta:
        model = HostelVisitor
        fields = ["status", "entry_time", "exit_time", "remarks"]
        widgets = {
            "status": forms.Select(attrs={"class": "form-control"}),
            "entry_time": forms.TimeInput(attrs={"class": "form-control", "type": "time"}),
            "exit_time": forms.TimeInput(attrs={"class": "form-control", "type": "time"}),
            "remarks": forms.Textarea(attrs={"class": "form-control", "rows": 3, "placeholder": "Warden / gate pass remarks..."}),
        }
