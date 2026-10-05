import os
from django.db import models, transaction
from django.contrib.auth.models import User
from django.utils import timezone
from students.models import Student


class CertificateType(models.Model):
    """
    Configurable certificate type with approval and PDF settings.
    Supports Bonafide, Course Completion, Transfer, Conduct, etc.
    """

    name = models.CharField(max_length=120)
    code = models.CharField(max_length=50, unique=True, help_text="Unique identifier e.g. BONAFIDE")
    description = models.TextField(blank=True, help_text="Description and instructions for students")
    requires_approval = models.BooleanField(
        default=True,
        help_text="Whether this certificate requires staff/admin approval before generation"
    )
    is_pdf_available = models.BooleanField(
        default=True,
        help_text="Whether automatic PDF generation is enabled for this certificate"
    )
    is_active = models.BooleanField(default=True, help_text="Whether students can request this certificate")
    template_content = models.TextField(
        blank=True,
        help_text="Custom wording template. Supports {student_name}, {roll_no}, {course_name}, {department_name}, {year}, {purpose}, {sif_number}."
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "Certificate Type"
        verbose_name_plural = "Certificate Types"

    def __str__(self):
        return self.name


class CertificateRequest(models.Model):
    """
    Formal certificate request submitted by a student.
    Follows lifecycle: Pending -> Under Review -> Approved / Rejected -> Generated -> Downloaded.
    """

    STATUS_PENDING = "Pending"
    STATUS_UNDER_REVIEW = "Under Review"
    STATUS_APPROVED = "Approved"
    STATUS_REJECTED = "Rejected"
    STATUS_GENERATED = "Generated"
    STATUS_DOWNLOADED = "Downloaded"

    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_UNDER_REVIEW, "Under Review"),
        (STATUS_APPROVED, "Approved"),
        (STATUS_REJECTED, "Rejected"),
        (STATUS_GENERATED, "Generated"),
        (STATUS_DOWNLOADED, "Downloaded"),
    ]

    request_id = models.CharField(
        max_length=32,
        unique=True,
        db_index=True,
        help_text="Unique Request Identifier (e.g. CERT-REQ-2026-000001)"
    )
    student = models.ForeignKey(
        Student,
        on_delete=models.CASCADE,
        related_name="certificate_requests"
    )
    certificate_type = models.ForeignKey(
        CertificateType,
        on_delete=models.PROTECT,
        related_name="requests"
    )
    purpose = models.CharField(max_length=255, help_text="Reason/purpose for requesting certificate")
    additional_remarks = models.TextField(blank=True, help_text="Optional remarks or notes from student")
    status = models.CharField(
        max_length=30,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING,
        db_index=True
    )
    rejection_reason = models.TextField(
        blank=True,
        help_text="Mandatory reason if request is rejected"
    )
    approved_by = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="approved_certificate_requests"
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Certificate Request"
        verbose_name_plural = "Certificate Requests"
        indexes = [
            models.Index(fields=["status", "student"]),
            models.Index(fields=["created_at"]),
        ]

    def __str__(self):
        return f"{self.request_id} - {self.student.name} ({self.certificate_type.name})"

    @classmethod
    def generate_next_request_id(cls):
        """Generates sequential, unique Request ID: CERT-REQ-YYYY-XXXXXX."""
        year = timezone.now().year
        prefix = f"CERT-REQ-{year}-"
        with transaction.atomic():
            last = cls.objects.filter(request_id__startswith=prefix).select_for_update().order_by("-request_id").first()
            if last and last.request_id:
                try:
                    last_num = int(last.request_id.split("-")[-1])
                    next_num = last_num + 1
                except (ValueError, IndexError):
                    next_num = 1
            else:
                next_num = 1
            return f"{prefix}{next_num:06d}"

    @property
    def is_active_pending(self):
        return self.status in [self.STATUS_PENDING, self.STATUS_UNDER_REVIEW]

    @property
    def status_badge_class(self):
        mapping = {
            self.STATUS_PENDING: "amber",
            self.STATUS_UNDER_REVIEW: "blue",
            self.STATUS_APPROVED: "green",
            self.STATUS_REJECTED: "rose",
            self.STATUS_GENERATED: "violet",
            self.STATUS_DOWNLOADED: "slate",
        }
        return mapping.get(self.status, "slate")


class GeneratedCertificate(models.Model):
    """
    Official generated certificate record linked to a request.
    Includes auto-generated unique certificate number (SC-CERT-YYYY-XXXXXX).
    """

    certificate_number = models.CharField(
        max_length=50,
        unique=True,
        db_index=True,
        help_text="Unique Certificate Number (e.g. SC-CERT-2026-000001)"
    )
    request = models.OneToOneField(
        CertificateRequest,
        on_delete=models.CASCADE,
        related_name="generated_certificate"
    )
    student = models.ForeignKey(
        Student,
        on_delete=models.CASCADE,
        related_name="generated_certificates"
    )
    certificate_type = models.ForeignKey(
        CertificateType,
        on_delete=models.PROTECT,
        related_name="generated_certificates"
    )
    issue_date = models.DateField(default=timezone.localdate)
    signatory_title = models.CharField(
        max_length=120,
        default="Principal / Academic Registrar"
    )
    pdf_file = models.FileField(
        upload_to="certificates/generated/%Y/%m/",
        null=True,
        blank=True
    )
    download_count = models.PositiveIntegerField(default=0)
    created_by = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="created_certificates"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Generated Certificate"
        verbose_name_plural = "Generated Certificates"

    def __str__(self):
        return f"{self.certificate_number} - {self.student.name} ({self.certificate_type.name})"

    @classmethod
    def generate_next_certificate_number(cls):
        """Generates sequential, unique Certificate Number: SC-CERT-YYYY-XXXXXX."""
        year = timezone.now().year
        prefix = f"SC-CERT-{year}-"
        with transaction.atomic():
            last = cls.objects.filter(certificate_number__startswith=prefix).select_for_update().order_by("-certificate_number").first()
            if last and last.certificate_number:
                try:
                    last_num = int(last.certificate_number.split("-")[-1])
                    next_num = last_num + 1
                except (ValueError, IndexError):
                    next_num = 1
            else:
                next_num = 1
            return f"{prefix}{next_num:06d}"


class StudentDocument(models.Model):
    """
    Student uploaded documents repository with staff verification workflow.
    Supports ID Proof, Address Proof, Marksheets, Transfer/Community Certificates, etc.
    """

    DOC_ID_PROOF = "ID Proof"
    DOC_ADDRESS_PROOF = "Address Proof"
    DOC_MARKSHEET = "Previous Marksheet"
    DOC_TRANSFER_CERT = "Transfer Certificate"
    DOC_COMMUNITY_CERT = "Community Certificate"
    DOC_INTERNSHIP_CERT = "Internship Certificate"
    DOC_OTHER = "Other Document"

    DOC_TYPE_CHOICES = [
        (DOC_ID_PROOF, "ID Proof"),
        (DOC_ADDRESS_PROOF, "Address Proof"),
        (DOC_MARKSHEET, "Previous Marksheet"),
        (DOC_TRANSFER_CERT, "Transfer Certificate"),
        (DOC_COMMUNITY_CERT, "Community Certificate"),
        (DOC_INTERNSHIP_CERT, "Internship Certificate"),
        (DOC_OTHER, "Other Document"),
    ]

    STATUS_PENDING = "Pending Verification"
    STATUS_VERIFIED = "Verified"
    STATUS_REJECTED = "Rejected"

    VERIFICATION_CHOICES = [
        (STATUS_PENDING, "Pending Verification"),
        (STATUS_VERIFIED, "Verified"),
        (STATUS_REJECTED, "Rejected"),
    ]

    student = models.ForeignKey(
        Student,
        on_delete=models.CASCADE,
        related_name="documents"
    )
    document_type = models.CharField(
        max_length=50,
        choices=DOC_TYPE_CHOICES,
        default=DOC_OTHER
    )
    title = models.CharField(max_length=150, help_text="Descriptive title of document")
    file = models.FileField(upload_to="documents/student_docs/%Y/%m/")
    uploaded_at = models.DateTimeField(auto_now_add=True)
    uploaded_by = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="uploaded_student_documents"
    )
    verification_status = models.CharField(
        max_length=30,
        choices=VERIFICATION_CHOICES,
        default=STATUS_PENDING,
        db_index=True
    )
    verified_by = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="verified_student_documents"
    )
    verified_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.TextField(blank=True, help_text="Reason if document verification was rejected")
    remarks = models.TextField(blank=True, help_text="Notes/remarks from student or staff")

    class Meta:
        ordering = ["-uploaded_at"]
        verbose_name = "Student Document"
        verbose_name_plural = "Student Documents"
        indexes = [
            models.Index(fields=["student", "verification_status"]),
        ]

    def __str__(self):
        return f"{self.title} - {self.student.name} ({self.document_type})"

    @property
    def filename(self):
        return os.path.basename(self.file.name) if self.file else ""

    @property
    def status_badge_class(self):
        mapping = {
            self.STATUS_PENDING: "amber",
            self.STATUS_VERIFIED: "green",
            self.STATUS_REJECTED: "rose",
        }
        return mapping.get(self.verification_status, "slate")
