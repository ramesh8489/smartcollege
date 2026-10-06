from decimal import Decimal
import secrets
import string

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

from faculty.models import Faculty
from students.models import Student

from .models import FeePayment, FeeRecord


def _student_for_request(request):
    return Student.objects.filter(user=request.user).select_related(
        "department", "course"
    ).first()


@login_required(login_url="/accounts/login/")
def fee_dashboard(request):
    student = _student_for_request(request)

    if request.user.is_superuser:
        records = list(
            FeeRecord.objects.select_related("student", "student__course", "student__department")
            .prefetch_related("payments")
            .order_by("-created_at")
        )
    elif student:
        records = list(
            FeeRecord.objects.filter(student=student)
            .select_related("student", "student__course", "student__department")
            .prefetch_related("payments")
            .order_by("-created_at")
        )
    else:
        # Faculty accounts do not get access to fee data by default.
        if Faculty.objects.filter(user=request.user).exists() or Faculty.objects.filter(email=request.user.email).exists():
            raise PermissionDenied
        records = []

    total_fee = sum((record.amount for record in records), Decimal("0.00"))
    total_paid = sum((record.paid_amount for record in records), Decimal("0.00"))
    total_balance = max(total_fee - total_paid, Decimal("0.00"))

    payments = []
    for record in records:
        for payment in record.payments.all():
            payments.append(payment)
    payments.sort(key=lambda payment: (payment.payment_date, payment.created_at), reverse=True)

    context = {
        "student": student,
        "records": records,
        "payments": payments[:20],
        "total_fee": total_fee,
        "total_paid": total_paid,
        "total_balance": total_balance,
        "record_count": len(records),
    }
    return render(request, "fees/dashboard.html", context)


@require_POST
@login_required(login_url="/accounts/login/")
def pay_fee(request, record_id):
    student = _student_for_request(request)
    if not student and not request.user.is_superuser:
        raise PermissionDenied

    fee_record = get_object_or_404(FeeRecord, pk=record_id)
    if not request.user.is_superuser and fee_record.student_id != student.id:
        raise PermissionDenied

    amount_str = request.POST.get("amount", "").strip()
    payment_mode = request.POST.get("payment_mode", "UPI").upper()
    reference_number = request.POST.get("reference_number", "").strip()

    try:
        amount = Decimal(amount_str)
    except Exception:
        if request.headers.get("x-requested-with") == "XMLHttpRequest" or "application/json" in request.headers.get("accept", ""):
            return JsonResponse({"success": False, "error": "Invalid payment amount entered."}, status=400)
        messages.error(request, "Invalid payment amount entered.")
        return redirect(request.META.get("HTTP_REFERER", "/fees/"))

    balance = fee_record.balance_amount
    if amount <= Decimal("0.00"):
        msg = "Payment amount must be greater than zero."
        if request.headers.get("x-requested-with") == "XMLHttpRequest" or "application/json" in request.headers.get("accept", ""):
            return JsonResponse({"success": False, "error": msg}, status=400)
        messages.error(request, msg)
        return redirect(request.META.get("HTTP_REFERER", "/fees/"))

    if amount > balance:
        msg = f"Payment amount ₹{amount:,.2f} exceeds remaining balance of ₹{balance:,.2f}."
        if request.headers.get("x-requested-with") == "XMLHttpRequest" or "application/json" in request.headers.get("accept", ""):
            return JsonResponse({"success": False, "error": msg}, status=400)
        messages.error(request, msg)
        return redirect(request.META.get("HTTP_REFERER", "/fees/"))

    valid_modes = dict(FeePayment.PAYMENT_MODE_CHOICES)
    if payment_mode not in valid_modes:
        payment_mode = "UPI"

    while True:
        rand_code = "".join(secrets.choice(string.digits) for _ in range(6))
        receipt_no = f"REC-{timezone.now().year}-{rand_code}"
        if not FeePayment.objects.filter(receipt_number=receipt_no).exists():
            break

    if not reference_number:
        rand_ref = "".join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(8))
        reference_number = f"{payment_mode}/TXN/{rand_ref}"

    payment = FeePayment.objects.create(
        fee_record=fee_record,
        receipt_number=receipt_no,
        amount=amount,
        payment_date=timezone.now().date(),
        payment_mode=payment_mode,
        reference_number=reference_number,
        remarks=f"Online payment via Student Portal ({payment_mode})"
    )

    is_ajax = (
        request.headers.get("x-requested-with") == "XMLHttpRequest"
        or "application/json" in request.headers.get("accept", "")
    )
    if is_ajax:
        return JsonResponse({
            "success": True,
            "message": f"Payment of ₹{amount:,.2f} completed successfully!",
            "payment_id": payment.id,
            "receipt_number": payment.receipt_number,
            "receipt_url": f"/fees/receipt/{payment.id}/",
            "amount_paid": float(amount),
            "remaining_balance": float(fee_record.balance_amount),
            "status": fee_record.computed_status,
        })

    messages.success(
        request,
        f"Payment of ₹{amount:,.2f} completed successfully! Receipt #{payment.receipt_number} generated."
    )
    return redirect(f"/fees/receipt/{payment.id}/")


@login_required(login_url="/accounts/login/")
def payment_receipt(request, payment_id):
    payment = get_object_or_404(
        FeePayment.objects.select_related(
            "fee_record", "fee_record__student", "fee_record__student__course",
            "fee_record__student__department",
        ),
        pk=payment_id,
    )

    student = _student_for_request(request)
    if not request.user.is_superuser:
        if student is None or payment.fee_record.student_id != student.id:
            raise PermissionDenied

    response = HttpResponse(content_type="application/pdf")
    response["Content-Disposition"] = f'inline; filename="receipt-{payment.receipt_number}.pdf"'

    document = SimpleDocTemplate(
        response, pagesize=A4, rightMargin=36, leftMargin=36, topMargin=36, bottomMargin=36
    )
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        "ReceiptTitle",
        parent=styles["Title"],
        fontSize=18,
        leading=22,
        textColor=colors.HexColor("#1e3a8a"),
        alignment=1,
        fontName="Helvetica-Bold",
    )
    subtitle_style = ParagraphStyle(
        "ReceiptSubtitle",
        parent=styles["Normal"],
        fontSize=10,
        leading=14,
        textColor=colors.HexColor("#475569"),
        alignment=1,
    )
    badge_style = ParagraphStyle(
        "ReceiptBadge",
        parent=styles["Heading2"],
        fontSize=12,
        leading=16,
        textColor=colors.HexColor("#0f172a"),
        alignment=1,
        fontName="Helvetica-Bold",
    )
    cell_bold = ParagraphStyle(
        "CellBold",
        parent=styles["Normal"],
        fontSize=9,
        leading=13,
        fontName="Helvetica-Bold",
        textColor=colors.HexColor("#1e293b"),
    )
    cell_normal = ParagraphStyle(
        "CellNormal",
        parent=styles["Normal"],
        fontSize=9,
        leading=13,
        textColor=colors.HexColor("#0f172a"),
    )
    footer_style = ParagraphStyle(
        "ReceiptFooter",
        parent=styles["Italic"],
        fontSize=8,
        leading=11,
        textColor=colors.HexColor("#64748b"),
        alignment=1,
    )

    record = payment.fee_record
    student_obj = record.student

    elements = [
        Paragraph("TAKSHASHILA UNIVERSITY · SMART COLLEGE", title_style),
        Paragraph("Office of Student Accounts & Finance · University ERP System", subtitle_style),
        Spacer(1, 8),
        Paragraph("OFFICIAL FEE PAYMENT RECEIPT", badge_style),
        Spacer(1, 12),
    ]

    table_data = [
        [Paragraph("Receipt Number", cell_bold), Paragraph(f"<b>{payment.receipt_number}</b>", cell_bold)],
        [Paragraph("Payment Date", cell_bold), Paragraph(payment.payment_date.strftime("%d %B %Y"), cell_normal)],
        [Paragraph("Student Name", cell_bold), Paragraph(student_obj.name, cell_bold)],
        [Paragraph("Roll Number", cell_bold), Paragraph(student_obj.roll_no, cell_bold)],
        [Paragraph("University SIF Number", cell_bold), Paragraph(f"<b>{student_obj.sif_number or 'N/A'}</b>", cell_bold)],
        [Paragraph("School / Department", cell_bold), Paragraph(student_obj.department.name if student_obj.department else "—", cell_normal)],
        [Paragraph("Degree / Programme", cell_bold), Paragraph(str(student_obj.course) if student_obj.course else "—", cell_normal)],
        [Paragraph("Academic Year / Sem", cell_bold), Paragraph(f"{record.academic_year}" + (f" · Semester {record.semester}" if record.semester else ""), cell_normal)],
        [Paragraph("Fee Description", cell_bold), Paragraph(record.title, cell_normal)],
        [Paragraph("Fee Category", cell_bold), Paragraph(record.get_fee_type_display(), cell_normal)],
        [Paragraph("Payment Mode", cell_bold), Paragraph(payment.get_payment_mode_display(), cell_normal)],
        [Paragraph("Transaction Reference", cell_bold), Paragraph(payment.reference_number or "—", cell_normal)],
        [Paragraph("Total Fee Payable", cell_bold), Paragraph(f"₹{record.amount:,.2f}", cell_normal)],
        [Paragraph("Amount Paid This Receipt", cell_bold), Paragraph(f"<font color='#16a34a'><b>₹{payment.amount:,.2f}</b></font>", cell_bold)],
        [Paragraph("Remaining Due Balance", cell_bold), Paragraph(f"₹{record.balance_amount:,.2f}", cell_normal)],
        [Paragraph("Payment Status", cell_bold), Paragraph(f"<b>{record.computed_status}</b>", cell_bold)],
    ]

    col_widths = [150, 370]
    t = Table(table_data, colWidths=col_widths)
    t.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#f8fafc")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("BACKGROUND", (0, 13), (-1, 13), colors.HexColor("#f0fdf4")),
    ]))
    elements.append(t)
    elements.append(Spacer(1, 16))

    elements.append(Paragraph(
        f"✓ This is an authentic computer-generated receipt issued by Smart College ERP.<br/>"
        f"University SIF verification: <b>{student_obj.sif_number or 'N/A'}</b> · "
        f"Receipt timestamp: {timezone.now().strftime('%d %b %Y, %I:%M %p')}.",
        footer_style
    ))

    document.build(elements)
    return response
