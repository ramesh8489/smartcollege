from django import forms
from django.utils import timezone
from .models import StudentLeaveRequest, validate_leave_document


class StudentLeaveApplyForm(forms.ModelForm):
    class Meta:
        model = StudentLeaveRequest
        fields = [
            "leave_type",
            "from_date",
            "to_date",
            "reason",
            "supporting_document",
            "student_remarks",
        ]
        widgets = {
            "leave_type": forms.Select(attrs={"class": "select", "id": "id_leave_type"}),
            "from_date": forms.DateInput(attrs={"class": "input", "type": "date", "id": "id_from_date"}),
            "to_date": forms.DateInput(attrs={"class": "input", "type": "date", "id": "id_to_date"}),
            "reason": forms.Textarea(attrs={
                "class": "textarea",
                "rows": 4,
                "placeholder": "Provide detailed reason for the leave...",
                "id": "id_reason",
            }),
            "supporting_document": forms.ClearableFileInput(attrs={
                "class": "input",
                "id": "id_supporting_document",
                "accept": ".pdf,.jpg,.jpeg,.png",
            }),
            "student_remarks": forms.Textarea(attrs={
                "class": "textarea",
                "rows": 2,
                "placeholder": "Any additional remarks (optional)...",
                "id": "id_student_remarks",
            }),
        }

    def __init__(self, *args, **kwargs):
        self.student = kwargs.pop("student", None)
        super().__init__(*args, **kwargs)

    def clean(self):
        cleaned_data = super().clean()
        from_date = cleaned_data.get("from_date")
        to_date = cleaned_data.get("to_date")
        leave_type = cleaned_data.get("leave_type")

        if from_date and to_date:
            if from_date > to_date:
                self.add_error("from_date", "From date cannot be after To date.")

            today = timezone.localdate() if hasattr(timezone, "localdate") else timezone.now().date()
            if from_date < today:
                allowed_retroactive = [
                    StudentLeaveRequest.TYPE_SICK,
                    StudentLeaveRequest.TYPE_MEDICAL,
                    StudentLeaveRequest.TYPE_EMERGENCY,
                ]
                if leave_type not in allowed_retroactive:
                    self.add_error(
                        "from_date",
                        "Past-date leave requests are strictly allowed only for Medical, Sick, or Emergency leaves."
                    )
                else:
                    delta = (today - from_date).days
                    if delta > 7:
                        self.add_error(
                            "from_date",
                            "Past-date leave requests cannot exceed 7 days prior to today."
                        )

            # Prevent duplicate overlapping leave requests
            if self.student:
                inactive_statuses = [
                    StudentLeaveRequest.STATUS_CANCELLED,
                    StudentLeaveRequest.STATUS_FACULTY_REJECTED,
                    StudentLeaveRequest.STATUS_INCHARGE_REJECTED,
                    StudentLeaveRequest.STATUS_ADMIN_REJECTED,
                ]
                overlap_qs = StudentLeaveRequest.objects.filter(
                    student=self.student,
                    from_date__lte=to_date,
                    to_date__gte=from_date,
                ).exclude(status__in=inactive_statuses)

                if self.instance and self.instance.pk:
                    overlap_qs = overlap_qs.exclude(pk=self.instance.pk)

                if overlap_qs.exists():
                    existing = overlap_qs.first()
                    raise forms.ValidationError(
                        f"An active leave request ({existing.from_date} to {existing.to_date}, Status: {existing.status}) already overlaps with these dates."
                    )

        return cleaned_data


class LeaveActionForm(forms.Form):
    ACTION_CHOICES = [
        ("approve", "Approve"),
        ("reject", "Reject"),
    ]
    action = forms.ChoiceField(
        choices=ACTION_CHOICES,
        widget=forms.RadioSelect(attrs={"class": "action-radio"}),
        required=True,
    )
    remarks = forms.CharField(
        widget=forms.Textarea(attrs={
            "class": "textarea",
            "rows": 3,
            "placeholder": "Enter decision remarks / comments...",
            "required": True,
        }),
        required=False,
    )
