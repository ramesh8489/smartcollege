import os
from django.utils import timezone
from django.db import transaction
from django.contrib.auth.models import User
from students.models import Student
from faculty.models import Faculty
from timetable.models import Notification
from .models import CertificateType, CertificateRequest, GeneratedCertificate, StudentDocument


def notify_user(user, title, message, link=""):
    """Creates a notification using the existing SmartCollege Notification system."""
    if user and user.is_authenticated:
        try:
            Notification.objects.create(
                recipient=user,
                title=title,
                message=message,
                link=link or "/certificates/",
            )
        except Exception:
            pass


def get_user_role(user):
    """
    Identifies the authenticated user's role in the certificate system:
    - admin: superuser or staff
    - student: linked Student profile
    - faculty: linked Faculty profile
    """
    student = Student.objects.filter(user=user).select_related("course", "department").first()
    faculty = Faculty.objects.filter(user=user).first() or Faculty.objects.filter(email=user.email).first()
    is_admin = bool(user and (user.is_superuser or user.is_staff))

    if is_admin:
        role = "admin"
    elif student:
        role = "student"
    elif faculty:
        role = "faculty"
    else:
        role = "guest"

    return {
        "role": role,
        "student": student,
        "faculty": faculty,
        "is_admin": is_admin,
        "is_officer": is_admin,
    }


def seed_default_certificate_types():
    """Initializes standard college certificate types if not already present."""
    default_types = [
        {
            "code": "BONAFIDE",
            "name": "Bonafide Certificate",
            "description": "Certifies that the student is a genuine bonafide student currently enrolled at the institution.",
            "requires_approval": True,
            "is_pdf_available": True,
            "template_content": "This is to certify that {student_name}, Roll No: {roll_no} (SIF: {sif_number}), is a bonafide student of {course_name} in the {department_name}, pursuing Year {year} for the current academic session. This certificate is issued for the purpose of: {purpose}.",
        },
        {
            "code": "COURSE_COMPLETION",
            "name": "Course Completion Certificate",
            "description": "Certifies that the student has successfully completed the curriculum requirements.",
            "requires_approval": True,
            "is_pdf_available": True,
            "template_content": "This is to certify that {student_name}, Roll No: {roll_no}, has successfully completed all academic and practical requirements for the degree of {course_name} under the {department_name}.",
        },
        {
            "code": "TRANSFER",
            "name": "Transfer Certificate",
            "description": "Official institutional Transfer Certificate (TC) issued upon departure or completion.",
            "requires_approval": True,
            "is_pdf_available": True,
            "template_content": "This is to certify that {student_name}, Roll No: {roll_no}, was a student of {course_name} in the {department_name}. There are no disciplinary actions pending against the student and institutional transfer is granted.",
        },
        {
            "code": "CONDUCT",
            "name": "Conduct Certificate",
            "description": "Certifies the disciplinary record and student conduct during institutional enrollment.",
            "requires_approval": True,
            "is_pdf_available": True,
            "template_content": "This is to certify that during the period of study in {course_name}, the conduct and character of {student_name} (Roll No: {roll_no}) have been exemplary and satisfactory.",
        },
        {
            "code": "CHARACTER",
            "name": "Character Certificate",
            "description": "Certifies character and integrity for employment, higher studies, or government applications.",
            "requires_approval": True,
            "is_pdf_available": True,
            "template_content": "This is to certify that {student_name}, Roll No: {roll_no}, is known to the institution as a student of {course_name} and bears a good moral character.",
        },
        {
            "code": "STUDY",
            "name": "Study Certificate",
            "description": "Official study certificate verifying medium of instruction, duration, and course enrollment.",
            "requires_approval": True,
            "is_pdf_available": True,
            "template_content": "This is to certify that {student_name}, Roll No: {roll_no}, is studying {course_name} in the {department_name} with English as the medium of instruction.",
        },
        {
            "code": "NO_DUE",
            "name": "No Due Certificate",
            "description": "Institutional clearance certificate confirming no outstanding dues in fees, library, or labs.",
            "requires_approval": True,
            "is_pdf_available": True,
            "template_content": "This is to certify that {student_name}, Roll No: {roll_no}, has cleared all institutional dues across Department, Library, Laboratories, and Accounts.",
        },
        {
            "code": "INTERNSHIP",
            "name": "Internship Certificate",
            "description": "No Objection / Recommendation Certificate for off-campus internships and industrial training.",
            "requires_approval": True,
            "is_pdf_available": True,
            "template_content": "This is to certify that the institution has No Objection to {student_name} (Roll No: {roll_no}) of {course_name} undertaking practical internship and industrial training for {purpose}.",
        },
        {
            "code": "PROVISIONAL",
            "name": "Provisional Certificate",
            "description": "Provisional degree certificate issued pending formal university convocation.",
            "requires_approval": True,
            "is_pdf_available": True,
            "template_content": "This is to certify that {student_name}, Roll No: {roll_no}, has qualified for the award of the Degree of {course_name} under {department_name}.",
        },
        {
            "code": "MIGRATION",
            "name": "Migration Certificate",
            "description": "Certificate enabling student admission and migration to another university or state board.",
            "requires_approval": True,
            "is_pdf_available": True,
            "template_content": "This institution has no objection to {student_name} (Roll No: {roll_no}) continuing their higher education at another recognized university or institution.",
        },
        {
            "code": "CUSTOM",
            "name": "Custom Certificate",
            "description": "Custom or bespoke institutional certification issued upon specific student request.",
            "requires_approval": True,
            "is_pdf_available": True,
            "template_content": "This is to certify that {student_name}, Roll No: {roll_no}, of {course_name} in the {department_name}, is issued this certificate for the purpose of: {purpose}.",
        },
    ]

    created_count = 0
    for item in default_types:
        obj, created = CertificateType.objects.get_or_create(
            code=item["code"],
            defaults={
                "name": item["name"],
                "description": item["description"],
                "requires_approval": item["requires_approval"],
                "is_pdf_available": item["is_pdf_available"],
                "is_active": True,
                "template_content": item["template_content"],
            }
        )
        if created:
            created_count += 1
    return created_count


def generate_certificate_for_request(req, user=None, signatory_title="Principal / Academic Registrar"):
    """
    Creates or updates the GeneratedCertificate for an approved request,
    allocates a unique certificate number, renders the PDF, and updates status.
    """
    with transaction.atomic():
        cert = getattr(req, "generated_certificate", None)
        if not cert:
            cert_num = GeneratedCertificate.generate_next_certificate_number()
            cert = GeneratedCertificate.objects.create(
                certificate_number=cert_num,
                request=req,
                student=req.student,
                certificate_type=req.certificate_type,
                issue_date=timezone.localdate(),
                signatory_title=signatory_title,
                created_by=user,
            )
        else:
            if not cert.certificate_number:
                cert.certificate_number = GeneratedCertificate.generate_next_certificate_number()
            cert.signatory_title = signatory_title
            cert.save()

        # Generate and save the PDF file
        from .pdf_generator import render_certificate_pdf
        pdf_bytes = render_certificate_pdf(cert)

        from django.core.files.base import ContentFile
        filename = f"{cert.certificate_number}.pdf"
        cert.pdf_file.save(filename, ContentFile(pdf_bytes), save=True)

        # Update request status to Generated
        req.status = CertificateRequest.STATUS_GENERATED
        req.save(update_fields=["status", "updated_at"])

        # Notify student
        if req.student.user:
            notify_user(
                req.student.user,
                title=f"Certificate Ready: {cert.certificate_number}",
                message=f"Your {req.certificate_type.name} has been generated with Certificate No. {cert.certificate_number}. You can now download it.",
                link=f"/certificates/detail/{req.pk}/",
            )

        return cert
