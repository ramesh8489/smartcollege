from django import forms
from django.core.exceptions import ValidationError
from .models import Exam, ExamSchedule, StudentExamMark
from faculty.models import Subject
from students.models import Student


class ExamForm(forms.ModelForm):
    class Meta:
        model = Exam
        fields = [
            "name",
            "exam_type",
            "academic_year",
            "semester",
            "course",
            "year",
            "start_date",
            "end_date",
            "description",
            "is_active",
        ]
        widgets = {
            "name": forms.TextInput(attrs={
                "class": "input",
                "placeholder": "e.g. Continuous Assessment Test 1 (CAT-1) 2026",
                "required": True,
            }),
            "exam_type": forms.Select(attrs={"class": "select", "required": True}),
            "academic_year": forms.TextInput(attrs={
                "class": "input",
                "placeholder": "e.g. 2026-2027",
                "required": True,
            }),
            "semester": forms.Select(attrs={"class": "select", "required": True}),
            "course": forms.Select(attrs={"class": "select", "required": True}),
            "year": forms.Select(attrs={"class": "select", "required": True}),
            "start_date": forms.DateInput(attrs={
                "type": "date",
                "class": "input",
                "required": True,
            }),
            "end_date": forms.DateInput(attrs={
                "type": "date",
                "class": "input",
                "required": True,
            }),
            "description": forms.Textarea(attrs={
                "class": "textarea",
                "rows": 3,
                "placeholder": "Instructions, syllabus units, exam rules, or general notes...",
            }),
            "is_active": forms.CheckboxInput(attrs={
                "class": "checkbox-input",
            }),
        }

    def clean(self):
        cleaned_data = super().clean()
        start_date = cleaned_data.get("start_date")
        end_date = cleaned_data.get("end_date")

        if start_date and end_date:
            if end_date < start_date:
                raise ValidationError({
                    "end_date": "End date cannot be earlier than start date."
                })
        return cleaned_data


class ExamScheduleForm(forms.ModelForm):
    class Meta:
        model = ExamSchedule
        fields = [
            "subject",
            "exam_date",
            "start_time",
            "end_time",
            "room_number",
            "invigilator",
            "max_marks",
            "status",
        ]
        widgets = {
            "subject": forms.Select(attrs={"class": "select", "required": True}),
            "exam_date": forms.DateInput(attrs={"type": "date", "class": "input", "required": True}),
            "start_time": forms.TimeInput(attrs={"type": "time", "class": "input", "required": True}),
            "end_time": forms.TimeInput(attrs={"type": "time", "class": "input", "required": True}),
            "room_number": forms.TextInput(attrs={"class": "input", "placeholder": "e.g. Room 204 / Hall A"}),
            "invigilator": forms.Select(attrs={"class": "select"}),
            "max_marks": forms.NumberInput(attrs={"class": "input", "min": 1, "value": 100}),
            "status": forms.Select(attrs={"class": "select"}),
        }

    def __init__(self, *args, **kwargs):
        exam = kwargs.pop("exam", None)
        super().__init__(*args, **kwargs)
        if exam:
            # Filter subjects by the exam's course
            course_subjects = Subject.objects.filter(course=exam.course)
            if exam.semester:
                sem_subjects = course_subjects.filter(semester=exam.semester)
                if sem_subjects.exists():
                    course_subjects = sem_subjects
            if course_subjects.exists():
                self.fields["subject"].queryset = course_subjects


class StudentExamMarkForm(forms.ModelForm):
    class Meta:
        model = StudentExamMark
        fields = [
            "student",
            "exam",
            "subject",
            "exam_schedule",
            "max_marks",
            "marks_obtained",
            "result_status",
            "remarks",
        ]
        widgets = {
            "student": forms.Select(attrs={"class": "select", "required": True}),
            "exam": forms.Select(attrs={"class": "select", "required": True}),
            "subject": forms.Select(attrs={"class": "select", "required": True}),
            "exam_schedule": forms.Select(attrs={"class": "select"}),
            "max_marks": forms.NumberInput(attrs={"class": "input", "min": 1}),
            "marks_obtained": forms.NumberInput(attrs={"class": "input", "step": "0.01", "min": 0}),
            "result_status": forms.Select(attrs={"class": "select"}),
            "remarks": forms.TextInput(attrs={"class": "input", "placeholder": "Optional remarks or feedback"}),
        }

    def clean(self):
        cleaned_data = super().clean()
        max_marks = cleaned_data.get("max_marks")
        marks_obtained = cleaned_data.get("marks_obtained")
        result_status = cleaned_data.get("result_status")

        if result_status == "Absent":
            cleaned_data["marks_obtained"] = 0
            return cleaned_data

        if marks_obtained is not None and max_marks is not None:
            if marks_obtained < 0:
                raise ValidationError({"marks_obtained": "Marks obtained cannot be negative."})
            if marks_obtained > max_marks:
                raise ValidationError({"marks_obtained": f"Marks obtained ({marks_obtained}) cannot be greater than maximum marks ({max_marks})."})

        return cleaned_data
