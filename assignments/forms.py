from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone
from .models import Assignment, AssignmentSubmission
from faculty.models import Subject
from students.models import Course


class AssignmentForm(forms.ModelForm):
    class Meta:
        model = Assignment
        fields = [
            "title",
            "assignment_type",
            "subject",
            "course",
            "year",
            "semester",
            "academic_year",
            "assigned_date",
            "submission_deadline",
            "max_marks",
            "attachment",
            "description",
            "instructions",
            "is_active",
        ]
        widgets = {
            "title": forms.TextInput(attrs={
                "class": "input",
                "placeholder": "e.g. Mini-Project 1: Convolutional Neural Network Implementation",
                "required": True,
            }),
            "assignment_type": forms.Select(attrs={"class": "select", "required": True}),
            "subject": forms.Select(attrs={"class": "select", "required": True}),
            "course": forms.Select(attrs={"class": "select", "required": True}),
            "year": forms.Select(attrs={"class": "select", "required": True}),
            "semester": forms.Select(attrs={"class": "select", "required": True}),
            "academic_year": forms.TextInput(attrs={
                "class": "input",
                "placeholder": "e.g. 2026-2027",
                "required": True,
            }),
            "assigned_date": forms.DateInput(format="%Y-%m-%d", attrs={
                "type": "date",
                "class": "input",
                "required": True,
            }),
            "submission_deadline": forms.DateTimeInput(format="%Y-%m-%dT%H:%M", attrs={
                "type": "datetime-local",
                "class": "input",
                "required": True,
            }),
            "max_marks": forms.NumberInput(attrs={
                "class": "input",
                "min": 1,
                "value": 100,
                "required": True,
            }),
            "attachment": forms.FileInput(attrs={
                "class": "input",
            }),
            "description": forms.Textarea(attrs={
                "class": "textarea",
                "rows": 3,
                "placeholder": "Overview and objectives of the assignment...",
            }),
            "instructions": forms.Textarea(attrs={
                "class": "textarea",
                "rows": 3,
                "placeholder": "Specific guidelines, report formatting, code constraints, submission format...",
            }),
            "is_active": forms.CheckboxInput(attrs={
                "class": "checkbox-input",
            }),
        }

    def __init__(self, *args, **kwargs):
        faculty = kwargs.pop("faculty", None)
        super().__init__(*args, **kwargs)

        if faculty:
            # Scoped to faculty assigned subjects
            from timetable.models import Timetable
            from django.db.models import Q
            tt_subs = Timetable.objects.filter(faculty=faculty).values_list("subject_id", flat=True)
            self.fields["subject"].queryset = Subject.objects.filter(
                Q(faculty=faculty) | Q(id__in=tt_subs)
            ).distinct()

        if self.instance and self.instance.pk:
            if self.instance.assigned_date:
                self.initial["assigned_date"] = self.instance.assigned_date.strftime("%Y-%m-%d")
            if self.instance.submission_deadline:
                self.initial["submission_deadline"] = timezone.localtime(self.instance.submission_deadline).strftime("%Y-%m-%dT%H:%M")

    def clean(self):
        cleaned_data = super().clean()
        assigned_date = cleaned_data.get("assigned_date")
        deadline = cleaned_data.get("submission_deadline")
        max_marks = cleaned_data.get("max_marks")

        if assigned_date and deadline:
            if deadline.date() < assigned_date:
                raise ValidationError({
                    "submission_deadline": f"Submission deadline ({deadline.strftime('%Y-%m-%d %H:%M')}) cannot be earlier than assigned date ({assigned_date})."
                })

        if max_marks is not None and max_marks <= 0:
            raise ValidationError({
                "max_marks": "Maximum marks must be a positive integer greater than zero."
            })

        return cleaned_data


class AssignmentSubmissionForm(forms.ModelForm):
    class Meta:
        model = AssignmentSubmission
        fields = ["submission_file", "student_remarks"]
        widgets = {
            "submission_file": forms.FileInput(attrs={
                "class": "input",
                "required": True,
            }),
            "student_remarks": forms.Textarea(attrs={
                "class": "textarea",
                "rows": 3,
                "placeholder": "Optional submission notes, repository links, or execution steps for the faculty evaluator...",
            }),
        }

    def clean_submission_file(self):
        file = self.cleaned_data.get("submission_file")
        if not file:
            raise ValidationError("Please select a file to submit.")
        return file


class SubmissionEvaluationForm(forms.ModelForm):
    class Meta:
        model = AssignmentSubmission
        fields = ["marks_obtained", "feedback", "status"]
        widgets = {
            "marks_obtained": forms.NumberInput(attrs={
                "class": "input",
                "step": "0.01",
                "min": 0,
                "placeholder": "0.00",
                "required": True,
            }),
            "feedback": forms.Textarea(attrs={
                "class": "textarea",
                "rows": 3,
                "placeholder": "Detailed faculty feedback, strengths, improvements, or criteria score breakdown...",
            }),
            "status": forms.Select(attrs={
                "class": "select",
            }),
        }

    def __init__(self, *args, **kwargs):
        self.assignment = kwargs.pop("assignment", None)
        super().__init__(*args, **kwargs)
        if self.assignment:
            self.fields["marks_obtained"].widget.attrs["max"] = self.assignment.max_marks
            self.fields["marks_obtained"].help_text = f"Maximum marks: {self.assignment.max_marks}"

    def clean_marks_obtained(self):
        marks = self.cleaned_data.get("marks_obtained")
        if marks is not None:
            if marks < 0:
                raise ValidationError("Marks obtained cannot be negative.")
            if self.assignment and marks > self.assignment.max_marks:
                raise ValidationError(f"Marks obtained ({marks}) cannot exceed maximum marks ({self.assignment.max_marks}).")
        return marks
