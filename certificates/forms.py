import os
from django import forms
from django.core.exceptions import ValidationError
from .models import CertificateType, CertificateRequest, StudentDocument, GeneratedCertificate


ALLOWED_DOCUMENT_EXTENSIONS = [".pdf", ".jpg", ".jpeg", ".png"]
MAX_DOCUMENT_SIZE = 5 * 1024 * 1024  # 5 MB


def validate_document_file(upload):
    """Validates file extension and size to ensure safe document uploads."""
    if not upload:
        return upload

    ext = os.path.splitext(upload.name)[1].lower()
    if ext not in ALLOWED_DOCUMENT_EXTENSIONS:
        allowed = ", ".join(ALLOWED_DOCUMENT_EXTENSIONS)
        raise ValidationError(f"Unsupported file format '{ext}'. Allowed file types: {allowed}.")

    if upload.size > MAX_DOCUMENT_SIZE:
        max_mb = MAX_DOCUMENT_SIZE / (1024 * 1024)
        raise ValidationError(f"File size exceeds the {max_mb:.0f} MB limit. Current size: {upload.size / (1024 * 1024):.2f} MB.")

    return upload


class CertificateRequestForm(forms.ModelForm):
    """Student certificate request submission form."""

    class Meta:
        model = CertificateRequest
        fields = ["certificate_type", "purpose", "additional_remarks"]
        widgets = {
            "certificate_type": forms.Select(attrs={"class": "select", "id": "id_certificate_type"}),
            "purpose": forms.TextInput(attrs={
                "class": "input",
                "placeholder": "e.g. Higher education application, Education loan, Passport verification",
                "required": True,
            }),
            "additional_remarks": forms.Textarea(attrs={
                "class": "input",
                "rows": 3,
                "placeholder": "Provide any relevant details or urgent requirements (optional)",
            }),
        }

    def __init__(self, *args, **kwargs):
        self.student = kwargs.pop("student", None)
        super().__init__(*args, **kwargs)
        self.fields["certificate_type"].queryset = CertificateType.objects.filter(is_active=True).order_by("name")

    def clean(self):
        cleaned_data = super().clean()
        cert_type = cleaned_data.get("certificate_type")

        if cert_type and not cert_type.is_active:
            raise ValidationError("This certificate type is currently not available for requests.")

        if self.student and cert_type:
            # Check for existing active requests for the same certificate type
            existing_active = CertificateRequest.objects.filter(
                student=self.student,
                certificate_type=cert_type,
                status__in=[CertificateRequest.STATUS_PENDING, CertificateRequest.STATUS_UNDER_REVIEW]
            ).exists()

            if existing_active:
                raise ValidationError(
                    f"You already have an active pending request for '{cert_type.name}'. "
                    f"Please wait for it to be processed before submitting another request."
                )

        return cleaned_data


class CertificateTypeForm(forms.ModelForm):
    """Admin configuration form for Certificate Types."""

    class Meta:
        model = CertificateType
        fields = [
            "name",
            "code",
            "description",
            "requires_approval",
            "is_pdf_available",
            "is_active",
            "template_content",
        ]
        widgets = {
            "name": forms.TextInput(attrs={"class": "input", "placeholder": "e.g. Bonafide Certificate"}),
            "code": forms.TextInput(attrs={"class": "input", "placeholder": "e.g. BONAFIDE"}),
            "description": forms.Textarea(attrs={"class": "input", "rows": 2, "placeholder": "Description of this certificate"}),
            "requires_approval": forms.CheckboxInput(attrs={"class": "checkbox"}),
            "is_pdf_available": forms.CheckboxInput(attrs={"class": "checkbox"}),
            "is_active": forms.CheckboxInput(attrs={"class": "checkbox"}),
            "template_content": forms.Textarea(attrs={
                "class": "input",
                "rows": 4,
                "placeholder": "Template text with {student_name}, {roll_no}, {course_name}, {department_name}, {year}, {purpose} tokens",
            }),
        }

    def clean_code(self):
        code = self.cleaned_data.get("code", "").strip().upper()
        # Ensure unique code excluding current instance
        qs = CertificateType.objects.filter(code=code)
        if self.instance and self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise ValidationError(f"A certificate type with code '{code}' already exists.")
        return code


class StudentDocumentUploadForm(forms.ModelForm):
    """Upload form for student identity and academic documents."""

    class Meta:
        model = StudentDocument
        fields = ["document_type", "title", "file", "remarks"]
        widgets = {
            "document_type": forms.Select(attrs={"class": "select"}),
            "title": forms.TextInput(attrs={
                "class": "input",
                "placeholder": "e.g. Aadhaar Card Front & Back / 10th Standard Marksheet",
                "required": True,
            }),
            "file": forms.FileInput(attrs={"class": "input", "accept": ".pdf,.jpg,.jpeg,.png", "required": True}),
            "remarks": forms.Textarea(attrs={"class": "input", "rows": 2, "placeholder": "Optional remarks"}),
        }

    def clean_file(self):
        f = self.cleaned_data.get("file")
        return validate_document_file(f)


class CertificateRejectForm(forms.Form):
    """Admin modal/rejection form requiring mandatory rejection reason."""
    rejection_reason = forms.CharField(
        widget=forms.Textarea(attrs={
            "class": "input",
            "rows": 3,
            "placeholder": "Provide specific reason for rejection (mandatory)",
            "required": True,
        }),
        required=True,
        help_text="Provide clear feedback on why this certificate request was rejected."
    )


class DocumentVerifyForm(forms.Form):
    """Admin verification action for uploaded student documents."""
    verification_status = forms.ChoiceField(
        choices=[
            (StudentDocument.STATUS_VERIFIED, "Verified (Accept)"),
            (StudentDocument.STATUS_REJECTED, "Rejected (Decline)"),
        ],
        widget=forms.Select(attrs={"class": "select", "id": "id_verification_status"})
    )
    rejection_reason = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            "class": "input",
            "rows": 2,
            "placeholder": "Mandatory if rejecting document",
        })
    )
    remarks = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            "class": "input",
            "placeholder": "Optional verification notes",
        })
    )

    def clean(self):
        cleaned = super().clean()
        status = cleaned.get("verification_status")
        reason = cleaned.get("rejection_reason", "").strip()

        if status == StudentDocument.STATUS_REJECTED and not reason:
            self.add_error("rejection_reason", "A rejection reason is strictly required when rejecting a document.")
        return cleaned
