import io
import os
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph, Frame
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.graphics.barcode import qr
from reportlab.graphics.shapes import Drawing
from reportlab.graphics import renderPDF


def draw_certificate_border(c, width, height):
    """Draws an ornate academic certificate border with gold and navy accents."""
    c.saveState()

    # Outer deep navy border
    c.setStrokeColor(colors.HexColor("#0f172a"))
    c.setLineWidth(4)
    c.rect(20, 20, width - 40, height - 40)

    # Gold accent inner border
    c.setStrokeColor(colors.HexColor("#d97706"))
    c.setLineWidth(1.5)
    c.rect(26, 26, width - 52, height - 52)

    # Thin innermost frame
    c.setStrokeColor(colors.HexColor("#cbd5e1"))
    c.setLineWidth(0.5)
    c.rect(30, 30, width - 60, height - 60)

    # Corner decorations
    c.setFillColor(colors.HexColor("#d97706"))
    for x in [26, width - 26]:
        for y in [26, height - 26]:
            c.circle(x, y, 4, fill=1, stroke=0)

    # Subtle background watermark
    c.saveState()
    c.setFont("Helvetica-Bold", 48)
    c.setFillColor(colors.HexColor("#f8fafc"))
    c.translate(width / 2, height / 2 - 20)
    c.rotate(18)
    c.drawCentredString(0, 0, "SMART COLLEGE")
    c.restoreState()

    c.restoreState()


def render_certificate_pdf(generated_cert, verification_base_url=""):
    """
    Renders an official high-resolution landscape A4 certificate as PDF bytes.
    Includes student details, unique certificate number, signature block, and QR code.
    """
    student = generated_cert.student
    cert_type = generated_cert.certificate_type
    req = generated_cert.request

    buf = io.BytesIO()
    page_w, page_h = landscape(A4)  # 841.89 x 595.27
    c = canvas.Canvas(buf, pagesize=(page_w, page_h))

    # 1. Background & Border
    draw_certificate_border(c, page_w, page_h)

    # 2. Header / Institution Details
    c.setFont("Helvetica-Bold", 20)
    c.setFillColor(colors.HexColor("#0f172a"))
    c.drawCentredString(page_w / 2, page_h - 70, "SMART COLLEGE OF ADVANCED TECHNOLOGY")

    c.setFont("Helvetica-Bold", 10)
    c.setFillColor(colors.HexColor("#b45309"))
    c.drawCentredString(page_w / 2, page_h - 88, "AFFILIATED TO TAKSHASHILA UNIVERSITY · ACCREDITED 'A++' GRADE BY NAAC")

    c.setFont("Helvetica", 8.5)
    c.setFillColor(colors.HexColor("#64748b"))
    c.drawCentredString(page_w / 2, page_h - 104, "Knowledge Boulevard, Innovation Corridor · Official Academic Certification · ISO 9001:2015")

    # Header horizontal rule
    c.setStrokeColor(colors.HexColor("#e2e8f0"))
    c.setLineWidth(1)
    c.line(70, page_h - 114, page_w - 70, page_h - 114)

    # 3. Certificate Title
    title_text = cert_type.name.upper()
    if not title_text.endswith("CERTIFICATE"):
        title_text += " CERTIFICATE"

    c.setFillColor(colors.HexColor("#0f2942"))
    c.setFont("Helvetica-Bold", 18)
    c.drawCentredString(page_w / 2, page_h - 146, title_text)

    # Small gold underline below title
    c.setStrokeColor(colors.HexColor("#d97706"))
    c.setLineWidth(2)
    c.line(page_w / 2 - 120, page_h - 154, page_w / 2 + 120, page_h - 154)

    # 4. Certificate Metadata Ribbons (Left: Certificate Number, Right: Issue Date)
    c.setFont("Helvetica-Bold", 9)
    c.setFillColor(colors.HexColor("#334155"))
    c.drawString(70, page_h - 180, f"Certificate No: {generated_cert.certificate_number}")
    c.drawRightString(page_w - 70, page_h - 180, f"Date of Issue: {generated_cert.issue_date.strftime('%d %B %Y')}")

    # 5. Formatted Body Text (Paragraph using Platypus inside Frame)
    styles = getSampleStyleSheet()
    body_style = ParagraphStyle(
        "CertBody",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=12,
        leading=22,
        alignment=4,  # Justified
        textColor=colors.HexColor("#1e293b"),
    )

    # Check for template replacement or generate comprehensive standard text
    dept_name = student.department.name if student.department else "General Department"
    course_name = student.course.name if student.course else "Undergraduate / Postgraduate Program"
    sif_display = student.sif_number or "N/A"
    purpose_display = req.purpose or "Educational and Official Purposes"

    if cert_type.template_content and "{student_name}" in cert_type.template_content:
        raw_text = cert_type.template_content.format(
            student_name=f"<b>{student.name}</b>",
            roll_no=f"<b>{student.roll_no}</b>",
            sif_number=f"<b>{sif_display}</b>",
            course_name=f"<b>{course_name}</b>",
            department_name=f"<b>{dept_name}</b>",
            year=f"<b>{student.year}</b>",
            purpose=f"<b>{purpose_display}</b>",
        )
    else:
        raw_text = (
            f"This is to certify that <b>{student.name}</b>, bearing Roll Number "
            f"<b>{student.roll_no}</b> (SIF No: <b>{sif_display}</b>), is a bonafide and registered student of "
            f"<b>{course_name}</b> in the <b>{dept_name}</b>, currently pursuing Year <b>{student.year}</b> "
            f"at this institution.<br/><br/>"
            f"This certificate is issued upon the official request of the student for the purpose of: "
            f"<b>{purpose_display}</b>.<br/><br/>"
            f"According to college records, the student's conduct and progress have been satisfactory throughout "
            f"their academic tenure."
        )

    para = Paragraph(raw_text, body_style)
    frame = Frame(70, 160, page_w - 140, 210, id="cert_body_frame", topPadding=0, bottomPadding=0, leftPadding=0, rightPadding=0)
    frame.addFromList([para], c)

    # 6. QR Code for Verification
    verify_url = f"{verification_base_url}/certificates/verify/{generated_cert.certificate_number}/"
    qr_widget = qr.QrCodeWidget(verify_url)
    bounds = qr_widget.getBounds()
    qw = bounds[2] - bounds[0]
    qh = bounds[3] - bounds[1]
    qr_size = 62
    d = Drawing(qr_size, qr_size, transform=[qr_size / qw, 0, 0, qr_size / qh, 0, 0])
    d.add(qr_widget)
    renderPDF.draw(d, c, 70, 75)

    # QR Text
    c.setFont("Helvetica", 7.5)
    c.setFillColor(colors.HexColor("#64748b"))
    c.drawString(140, 115, "Scan QR to verify official authenticity")
    c.drawString(140, 102, f"ID: {generated_cert.certificate_number}")
    c.drawString(140, 89, "SmartCollege Verification Portal")

    # 7. Official Seal Graphic
    seal_x = page_w / 2
    seal_y = 105
    c.saveState()
    c.setStrokeColor(colors.HexColor("#b45309"))
    c.setLineWidth(1)
    c.circle(seal_x, seal_y, 32, fill=0, stroke=1)
    c.circle(seal_x, seal_y, 29, fill=0, stroke=1)
    c.setFont("Helvetica-Bold", 6)
    c.setFillColor(colors.HexColor("#b45309"))
    c.drawCentredString(seal_x, seal_y + 16, "★ SMART COLLEGE ★")
    c.drawCentredString(seal_x, seal_y - 2, "OFFICIAL SEAL")
    c.drawCentredString(seal_x, seal_y - 18, "ESTD 1998")
    c.restoreState()

    # 8. Signature Block
    sig_x = page_w - 70
    c.setStrokeColor(colors.HexColor("#0f172a"))
    c.setLineWidth(1)
    c.line(sig_x - 170, 115, sig_x, 115)

    c.setFont("Helvetica-Bold", 10)
    c.setFillColor(colors.HexColor("#0f172a"))
    c.drawRightString(sig_x, 98, generated_cert.signatory_title)

    c.setFont("Helvetica", 8)
    c.setFillColor(colors.HexColor("#64748b"))
    c.drawRightString(sig_x, 85, "Smart College of Advanced Technology")

    c.showPage()
    c.save()

    buf.seek(0)
    return buf.getvalue()
