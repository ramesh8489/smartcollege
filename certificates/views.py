import os
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponseForbidden, FileResponse, Http404, HttpResponse
from django.utils import timezone
from django.db.models import Q, Count
from django.core.paginator import Paginator
from django.urls import reverse

from .models import CertificateType, CertificateRequest, GeneratedCertificate, StudentDocument
from .forms import (
    CertificateRequestForm,
    CertificateTypeForm,
    StudentDocumentUploadForm,
    CertificateRejectForm,
    DocumentVerifyForm,
)
from .services import (
    get_user_role,
    notify_user,
    seed_default_certificate_types,
    generate_certificate_for_request,
)
from students.models import Student, Department, Course
from faculty.models import Faculty


# ============================================================
# 1. PUBLIC CERTIFICATE VERIFICATION (QR & PORTAL)
# ============================================================

def certificate_verify(request, certificate_number=None):
    """
    Publicly accessible certificate verification endpoint.
    Scanned by QR code or searched by certificate number.
    Only displays non-sensitive, verified institutional facts.
    """
    cert_num = (certificate_number or request.GET.get("cert_num", "")).strip().upper()
    cert = None
    searched = bool(cert_num)

    if cert_num:
        cert = (
            GeneratedCertificate.objects.filter(certificate_number=cert_num)
            .select_related("student__department", "student__course", "certificate_type")
            .first()
        )

    context = {
        "cert_num": cert_num,
        "cert": cert,
        "searched": searched,
        "is_valid": cert is not None,
    }
    return render(request, "certificates/verify.html", context)


# ============================================================
# 2. STUDENT CERTIFICATE & DOCUMENT PORTAL
# ============================================================

@login_required(login_url="/accounts/login/")
def student_portal(request):
    """
    Unified Student Portal:
    - Certificate requests summary, tracker, and new request modal/form
    - Uploaded documents repository and verification status
    """
    ctx_role = get_user_role(request.user)

    # Route administrators to the admin certificate dashboard
    if ctx_role["is_officer"] and not ctx_role["student"]:
        return redirect("certificates_admin_dashboard")

    student = ctx_role["student"]
    if not student:
        messages.error(request, "Enrolled student account required to access this portal.")
        return redirect("/accounts/login/")

    # Seed standard types if empty
    if not CertificateType.objects.exists():
        seed_default_certificate_types()

    # Form handling for quick request
    if request.method == "POST" and "request_certificate" in request.POST:
        req_form = CertificateRequestForm(request.POST, student=student)
        if req_form.is_valid():
            req_obj = req_form.save(commit=False)
            req_obj.student = student
            req_obj.request_id = CertificateRequest.generate_next_request_id()
            req_obj.status = CertificateRequest.STATUS_PENDING
            req_obj.save()

            messages.success(request, f"Certificate request '{req_obj.request_id}' submitted successfully!")
            notify_user(
                request.user,
                title=f"Request Submitted: {req_obj.request_id}",
                message=f"Your request for {req_obj.certificate_type.name} is received and pending review.",
                link=f"/certificates/detail/{req_obj.pk}/",
            )
            return redirect("certificates_student_portal")
        else:
            messages.error(request, "Please correct the errors in the certificate request form.")
    else:
        req_form = CertificateRequestForm(student=student)

    # Document upload form
    if request.method == "POST" and "upload_document" in request.POST:
        doc_form = StudentDocumentUploadForm(request.POST, request.FILES)
        if doc_form.is_valid():
            doc_obj = doc_form.save(commit=False)
            doc_obj.student = student
            doc_obj.uploaded_by = request.user
            doc_obj.verification_status = StudentDocument.STATUS_PENDING
            doc_obj.save()

            messages.success(request, f"Document '{doc_obj.title}' uploaded successfully. It is queued for staff verification.")
            return redirect("certificates_student_portal")
        else:
            messages.error(request, "Please provide a valid document file (PDF, JPG, PNG under 5MB).")
    else:
        doc_form = StudentDocumentUploadForm()

    # Requests & Documents Querysets
    my_requests = (
        CertificateRequest.objects.filter(student=student)
        .select_related("certificate_type", "generated_certificate")
        .order_by("-created_at")
    )
    my_docs = StudentDocument.objects.filter(student=student).order_by("-uploaded_at")

    # Metrics
    req_counts = {
        "total": my_requests.count(),
        "pending": my_requests.filter(status__in=[CertificateRequest.STATUS_PENDING, CertificateRequest.STATUS_UNDER_REVIEW]).count(),
        "approved": my_requests.filter(status=CertificateRequest.STATUS_APPROVED).count(),
        "generated": my_requests.filter(status__in=[CertificateRequest.STATUS_GENERATED, CertificateRequest.STATUS_DOWNLOADED]).count(),
    }
    doc_counts = {
        "total": my_docs.count(),
        "verified": my_docs.filter(verification_status=StudentDocument.STATUS_VERIFIED).count(),
        "pending": my_docs.filter(verification_status=StudentDocument.STATUS_PENDING).count(),
        "rejected": my_docs.filter(verification_status=StudentDocument.STATUS_REJECTED).count(),
    }

    context = {
        "student": student,
        "req_form": req_form,
        "doc_form": doc_form,
        "requests": my_requests[:10],
        "documents": my_docs,
        "req_counts": req_counts,
        "doc_counts": doc_counts,
        "active_tab": request.GET.get("tab", "requests"),
    }
    return render(request, "certificates/student_portal.html", context)


@login_required(login_url="/accounts/login/")
def certificate_request_create(request):
    """Dedicated page for submitting a new certificate request."""
    ctx_role = get_user_role(request.user)
    student = ctx_role["student"]
    if not student:
        messages.error(request, "Only enrolled students can request certificates.")
        return redirect("certificates_admin_dashboard" if ctx_role["is_officer"] else "/accounts/login/")

    if request.method == "POST":
        form = CertificateRequestForm(request.POST, student=student)
        if form.is_valid():
            req_obj = form.save(commit=False)
            req_obj.student = student
            req_obj.request_id = CertificateRequest.generate_next_request_id()
            req_obj.status = CertificateRequest.STATUS_PENDING
            req_obj.save()

            messages.success(request, f"Certificate request {req_obj.request_id} has been submitted!")
            notify_user(
                request.user,
                title=f"Certificate Requested: {req_obj.request_id}",
                message=f"Request for {req_obj.certificate_type.name} submitted successfully.",
                link=f"/certificates/detail/{req_obj.pk}/",
            )
            return redirect("certificates_student_portal")
    else:
        initial_type = request.GET.get("type")
        initial = {}
        if initial_type:
            ct = CertificateType.objects.filter(code=initial_type, is_active=True).first()
            if ct:
                initial["certificate_type"] = ct
        form = CertificateRequestForm(initial=initial, student=student)

    return render(request, "certificates/request_form.html", {"form": form, "student": student})


@login_required(login_url="/accounts/login/")
def student_certificate_history(request):
    """Full filterable and searchable history of student's certificate requests."""
    ctx_role = get_user_role(request.user)
    student = ctx_role["student"]
    if not student:
        return redirect("certificates_admin_dashboard" if ctx_role["is_officer"] else "/accounts/login/")

    qs = (
        CertificateRequest.objects.filter(student=student)
        .select_related("certificate_type", "generated_certificate")
        .order_by("-created_at")
    )

    # Filters
    q = request.GET.get("q", "").strip()
    status_filter = request.GET.get("status", "").strip()
    type_filter = request.GET.get("type", "").strip()
    date_filter = request.GET.get("date", "").strip()

    if q:
        qs = qs.filter(Q(request_id__icontains=q) | Q(purpose__icontains=q) | Q(certificate_type__name__icontains=q))
    if status_filter:
        qs = qs.filter(status=status_filter)
    if type_filter:
        qs = qs.filter(certificate_type__id=type_filter)
    if date_filter:
        qs = qs.filter(created_at__date=date_filter)

    paginator = Paginator(qs, 15)
    page_obj = paginator.get_page(request.GET.get("page", 1))

    cert_types = CertificateType.objects.filter(is_active=True).order_by("name")

    context = {
        "student": student,
        "page_obj": page_obj,
        "cert_types": cert_types,
        "q": q,
        "status_filter": status_filter,
        "type_filter": type_filter,
        "date_filter": date_filter,
        "status_choices": CertificateRequest.STATUS_CHOICES,
    }
    return render(request, "certificates/student_history.html", context)


# ============================================================
# 3. ADMIN & STAFF CERTIFICATE MANAGEMENT DASHBOARD
# ============================================================

@login_required(login_url="/accounts/login/")
def admin_dashboard(request):
    """
    Central Admin & Staff Dashboard for Certificate Requests:
    - Counters, comprehensive search and multi-dimensional filters
    - Quick workflow triggers
    """
    ctx_role = get_user_role(request.user)
    if not ctx_role["is_officer"]:
        return HttpResponseForbidden("Administrative privileges required to access certificate management.")

    # Seed if needed
    if not CertificateType.objects.exists():
        seed_default_certificate_types()

    today = timezone.localdate()
    all_requests = CertificateRequest.objects.all()

    # Metric Counters
    stats = {
        "total": all_requests.count(),
        "pending": all_requests.filter(status=CertificateRequest.STATUS_PENDING).count(),
        "under_review": all_requests.filter(status=CertificateRequest.STATUS_UNDER_REVIEW).count(),
        "approved": all_requests.filter(status=CertificateRequest.STATUS_APPROVED).count(),
        "rejected": all_requests.filter(status=CertificateRequest.STATUS_REJECTED).count(),
        "generated": all_requests.filter(status__in=[CertificateRequest.STATUS_GENERATED, CertificateRequest.STATUS_DOWNLOADED]).count(),
        "today": all_requests.filter(created_at__date=today).count(),
        "pending_docs": StudentDocument.objects.filter(verification_status=StudentDocument.STATUS_PENDING).count(),
    }

    # QuerySet filtering
    qs = all_requests.select_related(
        "student__department",
        "student__course",
        "certificate_type",
        "generated_certificate"
    ).order_by("-created_at")

    q = request.GET.get("q", "").strip()
    status_filter = request.GET.get("status", "").strip()
    type_filter = request.GET.get("type", "").strip()
    dept_filter = request.GET.get("dept", "").strip()
    course_filter = request.GET.get("course", "").strip()
    year_filter = request.GET.get("year", "").strip()
    date_filter = request.GET.get("date", "").strip()

    if q:
        qs = qs.filter(
            Q(request_id__icontains=q)
            | Q(student__name__icontains=q)
            | Q(student__roll_no__icontains=q)
            | Q(certificate_type__name__icontains=q)
            | Q(generated_certificate__certificate_number__icontains=q)
        )
    if status_filter:
        qs = qs.filter(status=status_filter)
    if type_filter:
        qs = qs.filter(certificate_type_id=type_filter)
    if dept_filter:
        qs = qs.filter(student__department_id=dept_filter)
    if course_filter:
        qs = qs.filter(student__course_id=course_filter)
    if year_filter:
        qs = qs.filter(student__year=year_filter)
    if date_filter:
        qs = qs.filter(created_at__date=date_filter)

    paginator = Paginator(qs, 20)
    page_obj = paginator.get_page(request.GET.get("page", 1))

    departments = Department.objects.all().order_by("name")
    courses = Course.objects.all().order_by("name")
    types = CertificateType.objects.all().order_by("name")

    context = {
        "stats": stats,
        "page_obj": page_obj,
        "departments": departments,
        "courses": courses,
        "types": types,
        "status_choices": CertificateRequest.STATUS_CHOICES,
        "q": q,
        "status_filter": status_filter,
        "type_filter": type_filter,
        "dept_filter": dept_filter,
        "course_filter": course_filter,
        "year_filter": year_filter,
        "date_filter": date_filter,
    }
    return render(request, "certificates/admin_dashboard.html", context)


# ============================================================
# 4. CERTIFICATE REQUEST DETAILS & WORKFLOW ACTIONS
# ============================================================

@login_required(login_url="/accounts/login/")
def certificate_request_detail(request, pk):
    """
    Detailed dossier for a certificate request:
    - Full student academic and contact information
    - Request metadata & current lifecycle status
    - Workflow actions: Mark Under Review, Approve, Reject (mandatory reason), Generate, Download
    """
    req_obj = get_object_or_404(
        CertificateRequest.objects.select_related(
            "student__department",
            "student__course",
            "certificate_type",
            "generated_certificate"
        ),
        pk=pk
    )

    ctx_role = get_user_role(request.user)
    is_owner = ctx_role["student"] and (req_obj.student == ctx_role["student"])

    if not (is_owner or ctx_role["is_officer"]):
        return HttpResponseForbidden("You do not have permission to view this certificate request.")

    # Student's uploaded verification documents
    student_documents = StudentDocument.objects.filter(student=req_obj.student).order_by("-uploaded_at")

    reject_form = CertificateRejectForm()

    context = {
        "req": req_obj,
        "student": req_obj.student,
        "cert": getattr(req_obj, "generated_certificate", None),
        "is_officer": ctx_role["is_officer"],
        "is_owner": is_owner,
        "student_documents": student_documents,
        "reject_form": reject_form,
    }
    return render(request, "certificates/request_detail.html", context)


@login_required(login_url="/accounts/login/")
def certificate_request_action(request, pk):
    """
    Processes administrative status transitions:
    - review: moves to 'Under Review'
    - approve: moves to 'Approved'
    - reject: requires rejection_reason and moves to 'Rejected'
    - generate: generates certificate number and PDF
    """
    if request.method != "POST":
        return redirect("certificate_request_detail", pk=pk)

    ctx_role = get_user_role(request.user)
    if not ctx_role["is_officer"]:
        return HttpResponseForbidden("Staff authorization required.")

    req_obj = get_object_or_404(CertificateRequest, pk=pk)
    action = request.POST.get("action")

    if action == "review":
        req_obj.status = CertificateRequest.STATUS_UNDER_REVIEW
        req_obj.save(update_fields=["status", "updated_at"])
        messages.info(request, f"Request {req_obj.request_id} is now Under Review.")
        if req_obj.student.user:
            notify_user(
                req_obj.student.user,
                title=f"Request In Review: {req_obj.request_id}",
                message=f"Your request for {req_obj.certificate_type.name} is now Under Review by college administration.",
                link=f"/certificates/detail/{req_obj.pk}/",
            )

    elif action == "approve":
        req_obj.status = CertificateRequest.STATUS_APPROVED
        req_obj.approved_by = request.user
        req_obj.approved_at = timezone.now()
        req_obj.save(update_fields=["status", "approved_by", "approved_at", "updated_at"])
        messages.success(request, f"Request {req_obj.request_id} has been Approved.")
        if req_obj.student.user:
            notify_user(
                req_obj.student.user,
                title=f"Request Approved: {req_obj.request_id}",
                message=f"Your request for {req_obj.certificate_type.name} has been Approved.",
                link=f"/certificates/detail/{req_obj.pk}/",
            )

    elif action == "reject":
        reason = request.POST.get("rejection_reason", "").strip()
        if not reason:
            messages.error(request, "A rejection reason is mandatory when rejecting a certificate request.")
            return redirect("certificate_request_detail", pk=pk)

        req_obj.status = CertificateRequest.STATUS_REJECTED
        req_obj.rejection_reason = reason
        req_obj.save(update_fields=["status", "rejection_reason", "updated_at"])
        messages.warning(request, f"Request {req_obj.request_id} was Rejected.")
        if req_obj.student.user:
            notify_user(
                req_obj.student.user,
                title=f"Request Rejected: {req_obj.request_id}",
                message=f"Your request for {req_obj.certificate_type.name} was rejected. Reason: {reason}",
                link=f"/certificates/detail/{req_obj.pk}/",
            )

    elif action == "generate":
        signatory_title = request.POST.get("signatory_title", "Principal / Academic Registrar").strip()
        if req_obj.status not in [CertificateRequest.STATUS_APPROVED, CertificateRequest.STATUS_GENERATED]:
            # Auto-approve if generating directly
            req_obj.status = CertificateRequest.STATUS_APPROVED
            req_obj.approved_by = request.user
            req_obj.approved_at = timezone.now()
            req_obj.save()

        cert = generate_certificate_for_request(req_obj, user=request.user, signatory_title=signatory_title)
        messages.success(request, f"Certificate successfully generated! Certificate No: {cert.certificate_number}")

    return redirect("certificate_request_detail", pk=pk)


# ============================================================
# 5. SECURE CERTIFICATE PDF DOWNLOAD
# ============================================================

@login_required(login_url="/accounts/login/")
def download_certificate_pdf(request, pk):
    """
    Secure authenticated certificate download.
    Generates PDF on-the-fly if not already persisted to disk.
    Increments download count and updates status to 'Downloaded' for students.
    """
    req_obj = get_object_or_404(
        CertificateRequest.objects.select_related("student", "certificate_type", "generated_certificate"),
        pk=pk
    )

    ctx_role = get_user_role(request.user)
    is_owner = ctx_role["student"] and (req_obj.student == ctx_role["student"])

    if not (is_owner or ctx_role["is_officer"]):
        return HttpResponseForbidden("Unauthorized access to this certificate.")

    cert = getattr(req_obj, "generated_certificate", None)
    if not cert:
        if ctx_role["is_officer"]:
            cert = generate_certificate_for_request(req_obj, user=request.user)
        else:
            raise Http404("Certificate has not been generated yet.")

    # Increment download counter and update status
    cert.download_count += 1
    cert.save(update_fields=["download_count"])

    if req_obj.status == CertificateRequest.STATUS_GENERATED and is_owner:
        req_obj.status = CertificateRequest.STATUS_DOWNLOADED
        req_obj.save(update_fields=["status", "updated_at"])

    # If physical file exists, stream it
    if cert.pdf_file and os.path.exists(cert.pdf_file.path):
        response = FileResponse(open(cert.pdf_file.path, "rb"), content_type="application/pdf")
        filename = f"{cert.certificate_number}.pdf"
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        return response

    # Otherwise render dynamically
    from .pdf_generator import render_certificate_pdf
    host = request.build_absolute_uri("/").rstrip("/")
    pdf_bytes = render_certificate_pdf(cert, verification_base_url=host)

    response = HttpResponse(pdf_bytes, content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="{cert.certificate_number}.pdf"'
    return response


# ============================================================
# 6. DOCUMENT MANAGEMENT (STUDENT & ADMIN)
# ============================================================

@login_required(login_url="/accounts/login/")
def student_documents_portal(request):
    """Student documents repository view."""
    ctx_role = get_user_role(request.user)
    student = ctx_role["student"]
    if not student:
        return redirect("admin_document_management" if ctx_role["is_officer"] else "/accounts/login/")

    if request.method == "POST":
        form = StudentDocumentUploadForm(request.POST, request.FILES)
        if form.is_valid():
            doc = form.save(commit=False)
            doc.student = student
            doc.uploaded_by = request.user
            doc.verification_status = StudentDocument.STATUS_PENDING
            doc.save()
            messages.success(request, f"Document '{doc.title}' uploaded successfully and submitted for verification.")
            return redirect("student_documents_portal")
    else:
        form = StudentDocumentUploadForm()

    documents = StudentDocument.objects.filter(student=student).order_by("-uploaded_at")

    context = {
        "student": student,
        "form": form,
        "documents": documents,
        "doc_types": StudentDocument.DOC_TYPE_CHOICES,
    }
    return render(request, "certificates/student_documents.html", context)


@login_required(login_url="/accounts/login/")
def admin_document_management(request):
    """Admin dashboard for viewing and verifying student documents across the institution."""
    ctx_role = get_user_role(request.user)
    if not ctx_role["is_officer"]:
        return HttpResponseForbidden("Administrative privileges required.")

    qs = StudentDocument.objects.select_related("student__department", "student__course", "uploaded_by", "verified_by").order_by("-uploaded_at")

    q = request.GET.get("q", "").strip()
    status_filter = request.GET.get("status", "").strip()
    type_filter = request.GET.get("type", "").strip()
    dept_filter = request.GET.get("dept", "").strip()

    if q:
        qs = qs.filter(
            Q(title__icontains=q)
            | Q(student__name__icontains=q)
            | Q(student__roll_no__icontains=q)
        )
    if status_filter:
        qs = qs.filter(verification_status=status_filter)
    if type_filter:
        qs = qs.filter(document_type=type_filter)
    if dept_filter:
        qs = qs.filter(student__department_id=dept_filter)

    paginator = Paginator(qs, 20)
    page_obj = paginator.get_page(request.GET.get("page", 1))

    verify_form = DocumentVerifyForm()
    departments = Department.objects.all().order_by("name")

    stats = {
        "total": StudentDocument.objects.count(),
        "pending": StudentDocument.objects.filter(verification_status=StudentDocument.STATUS_PENDING).count(),
        "verified": StudentDocument.objects.filter(verification_status=StudentDocument.STATUS_VERIFIED).count(),
        "rejected": StudentDocument.objects.filter(verification_status=StudentDocument.STATUS_REJECTED).count(),
    }

    context = {
        "page_obj": page_obj,
        "verify_form": verify_form,
        "departments": departments,
        "doc_types": StudentDocument.DOC_TYPE_CHOICES,
        "status_choices": StudentDocument.VERIFICATION_CHOICES,
        "stats": stats,
        "q": q,
        "status_filter": status_filter,
        "type_filter": type_filter,
        "dept_filter": dept_filter,
    }
    return render(request, "certificates/admin_documents.html", context)


@login_required(login_url="/accounts/login/")
def admin_document_verify(request, pk):
    """Processes document verification (Verified or Rejected with mandatory reason)."""
    if request.method != "POST":
        return redirect("admin_document_management")

    ctx_role = get_user_role(request.user)
    if not ctx_role["is_officer"]:
        return HttpResponseForbidden("Staff privileges required.")

    doc = get_object_or_404(StudentDocument, pk=pk)
    form = DocumentVerifyForm(request.POST)

    if form.is_valid():
        new_status = form.cleaned_data["verification_status"]
        rejection_reason = form.cleaned_data["rejection_reason"]
        remarks = form.cleaned_data["remarks"]

        doc.verification_status = new_status
        doc.verified_by = request.user
        doc.verified_at = timezone.now()
        doc.rejection_reason = rejection_reason if new_status == StudentDocument.STATUS_REJECTED else ""
        if remarks:
            doc.remarks = remarks
        doc.save()

        if new_status == StudentDocument.STATUS_VERIFIED:
            messages.success(request, f"Document '{doc.title}' for {doc.student.name} marked Verified.")
            if doc.student.user:
                notify_user(
                    doc.student.user,
                    title="Document Verified",
                    message=f"Your document '{doc.title}' has been successfully verified.",
                    link="/documents/",
                )
        else:
            messages.warning(request, f"Document '{doc.title}' for {doc.student.name} rejected.")
            if doc.student.user:
                notify_user(
                    doc.student.user,
                    title="Document Verification Rejected",
                    message=f"Your document '{doc.title}' was rejected. Reason: {rejection_reason}",
                    link="/documents/",
                )
    else:
        for errs in form.errors.values():
            for err in errs:
                messages.error(request, err)

    return redirect(request.META.get("HTTP_REFERER") or "admin_document_management")


@login_required(login_url="/accounts/login/")
def download_student_document(request, pk):
    """
    Secure document file streaming.
    Only the student owner or an authorized administrator can download the file.
    """
    doc = get_object_or_404(StudentDocument, pk=pk)
    ctx_role = get_user_role(request.user)

    is_owner = ctx_role["student"] and (doc.student == ctx_role["student"])
    if not (is_owner or ctx_role["is_officer"]):
        return HttpResponseForbidden("Access Denied: You do not have permission to view or download this document.")

    if not doc.file or not os.path.exists(doc.file.path):
        raise Http404("Document file could not be found.")

    filename = os.path.basename(doc.file.path)
    response = FileResponse(open(doc.file.path, "rb"))
    response["Content-Disposition"] = f'inline; filename="{filename}"'
    return response


# ============================================================
# 7. CERTIFICATE TYPE CONFIGURATION (ADMIN)
# ============================================================

@login_required(login_url="/accounts/login/")
def certificate_type_list(request):
    """Admin configuration list for certificate types."""
    ctx_role = get_user_role(request.user)
    if not ctx_role["is_officer"]:
        return HttpResponseForbidden("Administrative privileges required.")

    types = CertificateType.objects.annotate(request_count=Count("requests")).order_by("name")
    return render(request, "certificates/type_list.html", {"types": types})


@login_required(login_url="/accounts/login/")
def certificate_type_create(request):
    """Admin adds a new Certificate Type."""
    ctx_role = get_user_role(request.user)
    if not ctx_role["is_officer"]:
        return HttpResponseForbidden("Administrative privileges required.")

    if request.method == "POST":
        form = CertificateTypeForm(request.POST)
        if form.is_valid():
            ct = form.save()
            messages.success(request, f"Certificate type '{ct.name}' created successfully.")
            return redirect("certificate_type_list")
    else:
        form = CertificateTypeForm()

    return render(request, "certificates/type_form.html", {"form": form, "title": "Add Certificate Type"})


@login_required(login_url="/accounts/login/")
def certificate_type_edit(request, pk):
    """Admin edits an existing Certificate Type."""
    ctx_role = get_user_role(request.user)
    if not ctx_role["is_officer"]:
        return HttpResponseForbidden("Administrative privileges required.")

    ct = get_object_or_404(CertificateType, pk=pk)
    if request.method == "POST":
        form = CertificateTypeForm(request.POST, instance=ct)
        if form.is_valid():
            form.save()
            messages.success(request, f"Certificate type '{ct.name}' updated successfully.")
            return redirect("certificate_type_list")
    else:
        form = CertificateTypeForm(instance=ct)

    return render(request, "certificates/type_form.html", {"form": form, "title": f"Edit {ct.name}", "ct": ct})


@login_required(login_url="/accounts/login/")
def certificate_type_toggle(request, pk):
    """Toggles active/inactive state of a certificate type."""
    ctx_role = get_user_role(request.user)
    if not ctx_role["is_officer"]:
        return HttpResponseForbidden("Administrative privileges required.")

    ct = get_object_or_404(CertificateType, pk=pk)
    ct.is_active = not ct.is_active
    ct.save(update_fields=["is_active", "updated_at"])
    state = "activated" if ct.is_active else "deactivated"
    messages.info(request, f"Certificate type '{ct.name}' is now {state}.")
    return redirect("certificate_type_list")
