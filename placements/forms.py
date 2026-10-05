from django import forms
from .models import (
    Company,
    PlacementDrive,
    PlacementApplication,
    PlacementRound,
    PlacementResult,
    StudentPlacementProfile,
)


class CompanyForm(forms.ModelForm):
    class Meta:
        model = Company
        fields = [
            "name",
            "logo",
            "industry",
            "website",
            "hr_contact_person",
            "contact_email",
            "contact_phone",
            "address",
            "description",
            "minimum_qualification",
            "status",
        ]
        widgets = {
            "name": forms.TextInput(attrs={"class": "input", "placeholder": "e.g. Google, Microsoft, TCS", "id": "id_company_name"}),
            "logo": forms.FileInput(attrs={"class": "input", "id": "id_company_logo", "accept": "image/*"}),
            "industry": forms.TextInput(attrs={"class": "input", "placeholder": "e.g. Information Technology, FinTech", "id": "id_company_industry"}),
            "website": forms.URLInput(attrs={"class": "input", "placeholder": "https://www.example.com", "id": "id_company_website"}),
            "hr_contact_person": forms.TextInput(attrs={"class": "input", "placeholder": "Lead Recruiter / HR Name", "id": "id_hr_contact"}),
            "contact_email": forms.EmailInput(attrs={"class": "input", "placeholder": "recruitment@example.com", "id": "id_contact_email"}),
            "contact_phone": forms.TextInput(attrs={"class": "input", "placeholder": "+91 98765 43210", "id": "id_contact_phone"}),
            "address": forms.Textarea(attrs={"class": "textarea", "rows": 3, "placeholder": "Corporate / Campus recruitment address", "id": "id_company_address"}),
            "description": forms.Textarea(attrs={"class": "textarea", "rows": 3, "placeholder": "Company overview and history...", "id": "id_company_desc"}),
            "minimum_qualification": forms.TextInput(attrs={"class": "input", "placeholder": "e.g. B.Tech / MCA", "id": "id_min_qual"}),
            "status": forms.Select(attrs={"class": "select", "id": "id_company_status"}),
        }


class PlacementDriveForm(forms.ModelForm):
    class Meta:
        model = PlacementDrive
        fields = [
            "company",
            "job_title",
            "job_description",
            "employment_type",
            "job_location",
            "salary_package",
            "salary_lpa",
            "minimum_percentage",
            "maximum_backlogs",
            "minimum_qualification",
            "eligible_departments",
            "eligible_courses",
            "eligible_year",
            "application_start_date",
            "application_deadline",
            "drive_date",
            "drive_location",
            "vacancies_count",
            "selection_process",
            "status",
            "description",
        ]
        widgets = {
            "company": forms.Select(attrs={"class": "select", "id": "id_drive_company"}),
            "job_title": forms.TextInput(attrs={"class": "input", "placeholder": "e.g. Associate Software Engineer", "id": "id_job_title"}),
            "job_description": forms.Textarea(attrs={"class": "textarea", "rows": 4, "placeholder": "Roles, responsibilities and requirements...", "id": "id_job_desc"}),
            "employment_type": forms.Select(attrs={"class": "select", "id": "id_emp_type"}),
            "job_location": forms.TextInput(attrs={"class": "input", "placeholder": "e.g. Bangalore, Hyderabad, Remote", "id": "id_job_location"}),
            "salary_package": forms.TextInput(attrs={"class": "input", "placeholder": "e.g. 8.5 LPA or 30,000/month", "id": "id_salary_package"}),
            "salary_lpa": forms.NumberInput(attrs={"class": "input", "placeholder": "e.g. 8.5", "step": "0.1", "id": "id_salary_lpa"}),
            "minimum_percentage": forms.NumberInput(attrs={"class": "input", "placeholder": "e.g. 65.0", "step": "0.1", "id": "id_min_pct"}),
            "maximum_backlogs": forms.NumberInput(attrs={"class": "input", "placeholder": "e.g. 0", "id": "id_max_backlogs"}),
            "minimum_qualification": forms.TextInput(attrs={"class": "input", "placeholder": "e.g. B.Tech / MCA", "id": "id_drive_qual"}),
            "eligible_departments": forms.SelectMultiple(attrs={"class": "select", "style": "min-height: 100px;", "id": "id_eligible_depts"}),
            "eligible_courses": forms.SelectMultiple(attrs={"class": "select", "style": "min-height: 100px;", "id": "id_eligible_courses"}),
            "eligible_year": forms.NumberInput(attrs={"class": "input", "placeholder": "4 for final year, 0 for all", "id": "id_eligible_year"}),
            "application_start_date": forms.DateInput(attrs={"class": "input", "type": "date", "id": "id_app_start"}),
            "application_deadline": forms.DateInput(attrs={"class": "input", "type": "date", "id": "id_app_deadline"}),
            "drive_date": forms.DateInput(attrs={"class": "input", "type": "date", "id": "id_drive_date"}),
            "drive_location": forms.TextInput(attrs={"class": "input", "placeholder": "e.g. Campus Auditorium / Virtual", "id": "id_drive_loc"}),
            "vacancies_count": forms.NumberInput(attrs={"class": "input", "placeholder": "Number of openings", "id": "id_vacancies"}),
            "selection_process": forms.Textarea(attrs={"class": "textarea", "rows": 3, "placeholder": "Round 1: Online Test, Round 2: Technical Interview...", "id": "id_selection_proc"}),
            "status": forms.Select(attrs={"class": "select", "id": "id_drive_status"}),
            "description": forms.Textarea(attrs={"class": "textarea", "rows": 3, "placeholder": "Additional guidelines or instructions...", "id": "id_drive_notes"}),
        }


class PlacementApplicationForm(forms.ModelForm):
    class Meta:
        model = PlacementApplication
        fields = ["resume", "cover_letter"]
        widgets = {
            "resume": forms.FileInput(attrs={"class": "input", "id": "id_app_resume", "accept": ".pdf,.doc,.docx"}),
            "cover_letter": forms.Textarea(attrs={
                "class": "textarea",
                "rows": 4,
                "placeholder": "Briefly state your motivation, key skills, and why you are a great fit for this role...",
                "id": "id_cover_letter",
            }),
        }


class PlacementRoundForm(forms.ModelForm):
    class Meta:
        model = PlacementRound
        fields = [
            "round_number",
            "round_name",
            "round_type",
            "scheduled_date",
            "start_time",
            "end_time",
            "location",
            "interviewer",
            "result",
            "score",
            "remarks",
        ]
        widgets = {
            "round_number": forms.NumberInput(attrs={"class": "input", "id": "id_round_num"}),
            "round_name": forms.TextInput(attrs={"class": "input", "placeholder": "e.g. Technical Coding Round", "id": "id_round_name"}),
            "round_type": forms.Select(attrs={"class": "select", "id": "id_round_type"}),
            "scheduled_date": forms.DateInput(attrs={"class": "input", "type": "date", "id": "id_round_date"}),
            "start_time": forms.TimeInput(attrs={"class": "input", "type": "time", "id": "id_round_start"}),
            "end_time": forms.TimeInput(attrs={"class": "input", "type": "time", "id": "id_round_end"}),
            "location": forms.TextInput(attrs={"class": "input", "placeholder": "Room 302 / Google Meet link", "id": "id_round_loc"}),
            "interviewer": forms.TextInput(attrs={"class": "input", "placeholder": "Interviewer name/panel", "id": "id_interviewer"}),
            "result": forms.Select(attrs={"class": "select", "id": "id_round_result"}),
            "score": forms.TextInput(attrs={"class": "input", "placeholder": "e.g. 85/100 or Excellent", "id": "id_round_score"}),
            "remarks": forms.Textarea(attrs={"class": "textarea", "rows": 3, "placeholder": "Feedback & performance remarks...", "id": "id_round_remarks"}),
        }


class PlacementResultForm(forms.ModelForm):
    class Meta:
        model = PlacementResult
        fields = [
            "job_title",
            "ctc",
            "joining_date",
            "placement_type",
            "offer_letter",
            "result",
            "remarks",
        ]
        widgets = {
            "job_title": forms.TextInput(attrs={"class": "input", "placeholder": "Designation offered", "id": "id_res_job_title"}),
            "ctc": forms.TextInput(attrs={"class": "input", "placeholder": "e.g. 9.2 LPA", "id": "id_res_ctc"}),
            "joining_date": forms.DateInput(attrs={"class": "input", "type": "date", "id": "id_res_joining_date"}),
            "placement_type": forms.Select(attrs={"class": "select", "id": "id_res_type"}),
            "offer_letter": forms.FileInput(attrs={"class": "input", "id": "id_res_offer_letter", "accept": ".pdf,.doc,.docx"}),
            "result": forms.Select(attrs={"class": "select", "id": "id_res_result"}),
            "remarks": forms.Textarea(attrs={"class": "textarea", "rows": 3, "placeholder": "Official congratulations or placement officer remarks...", "id": "id_res_remarks"}),
        }


class StudentPlacementProfileForm(forms.ModelForm):
    class Meta:
        model = StudentPlacementProfile
        fields = [
            "default_resume",
            "linkedin_url",
            "github_url",
            "portfolio_url",
            "skills",
            "bio",
            "cgpa_or_percentage",
            "active_backlogs",
        ]
        widgets = {
            "default_resume": forms.FileInput(attrs={"class": "input", "id": "id_prof_resume", "accept": ".pdf,.doc,.docx"}),
            "linkedin_url": forms.URLInput(attrs={"class": "input", "placeholder": "https://linkedin.com/in/...", "id": "id_linkedin"}),
            "github_url": forms.URLInput(attrs={"class": "input", "placeholder": "https://github.com/...", "id": "id_github"}),
            "portfolio_url": forms.URLInput(attrs={"class": "input", "placeholder": "https://myportfolio.dev", "id": "id_portfolio"}),
            "skills": forms.TextInput(attrs={"class": "input", "placeholder": "e.g. Python, Django, React, SQL, Java", "id": "id_skills"}),
            "bio": forms.Textarea(attrs={"class": "textarea", "rows": 3, "placeholder": "Professional summary...", "id": "id_bio"}),
            "cgpa_or_percentage": forms.NumberInput(attrs={"class": "input", "placeholder": "e.g. 78.5", "step": "0.1", "id": "id_cgpa"}),
            "active_backlogs": forms.NumberInput(attrs={"class": "input", "placeholder": "0", "id": "id_backlogs"}),
        }
