from django.contrib import admin
from .models import CertificateType, CertificateRequest, GeneratedCertificate, StudentDocument


@admin.register(CertificateType)
class CertificateTypeAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "requires_approval", "is_pdf_available", "is_active", "created_at")
    list_filter = ("is_active", "requires_approval", "is_pdf_available")
    search_fields = ("name", "code", "description")
    ordering = ("name",)


class GeneratedCertificateInline(admin.StackedInline):
    model = GeneratedCertificate
    extra = 0
    readonly_fields = ("certificate_number", "issue_date", "created_at", "download_count")


@admin.register(CertificateRequest)
class CertificateRequestAdmin(admin.ModelAdmin):
    list_display = ("request_id", "student", "certificate_type", "status", "created_at", "approved_by")
    list_filter = ("status", "certificate_type", "created_at")
    search_fields = ("request_id", "student__name", "student__roll_no", "purpose")
    readonly_fields = ("request_id", "created_at", "updated_at")
    inlines = [GeneratedCertificateInline]


@admin.register(GeneratedCertificate)
class GeneratedCertificateAdmin(admin.ModelAdmin):
    list_display = ("certificate_number", "student", "certificate_type", "issue_date", "download_count", "created_at")
    list_filter = ("certificate_type", "issue_date")
    search_fields = ("certificate_number", "student__name", "student__roll_no")
    readonly_fields = ("certificate_number", "created_at", "updated_at")


@admin.register(StudentDocument)
class StudentDocumentAdmin(admin.ModelAdmin):
    list_display = ("title", "student", "document_type", "verification_status", "uploaded_by", "uploaded_at", "verified_by")
    list_filter = ("document_type", "verification_status", "uploaded_at")
    search_fields = ("title", "student__name", "student__roll_no", "remarks")
    readonly_fields = ("uploaded_at",)
