"""
Bankka topshirish uchun professional biznes-reja PDF generatori (ReportLab).
"""
import os
from datetime import datetime
from typing import Any, Dict, List

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak,
)

from config import PDF_OUTPUT_DIR
from credit_calculator import LoanSchedule

styles = getSampleStyleSheet()
title_style = ParagraphStyle("TitleUz", parent=styles["Title"], fontSize=18, spaceAfter=14)
h2_style = ParagraphStyle("H2Uz", parent=styles["Heading2"], fontSize=13, spaceBefore=14, spaceAfter=6,
                           textColor=colors.HexColor("#1a3a6b"))
body_style = ParagraphStyle("BodyUz", parent=styles["Normal"], fontSize=10.5, leading=15)
note_style = ParagraphStyle("NoteUz", parent=styles["Normal"], fontSize=8.5, leading=12,
                             textColor=colors.HexColor("#666666"))


def _money(v: float) -> str:
    return f"{v:,.0f} so'm".replace(",", " ")


def build_business_plan_pdf(
    business_name: str,
    business_type: str,
    location: str,
    own_capital: float,
    cost_estimate: Dict[str, Any],
    loan_needed: float,
    loan_schedules: List[LoanSchedule],
) -> str:
    """PDF faylni yaratadi va uning to'liq yo'lini qaytaradi."""
    os.makedirs(PDF_OUTPUT_DIR, exist_ok=True)
    safe_name = "".join(c for c in business_name if c.isalnum() or c in " _-").strip().replace(" ", "_")
    filename = f"{safe_name or 'biznes_reja'}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    filepath = os.path.join(PDF_OUTPUT_DIR, filename)

    doc = SimpleDocTemplate(
        filepath, pagesize=A4,
        topMargin=18 * mm, bottomMargin=18 * mm, leftMargin=18 * mm, rightMargin=18 * mm,
    )
    story = []

    # --- Sarlavha ---
    story.append(Paragraph("BIZNES-REJA", title_style))
    story.append(Paragraph(f"<b>{business_name}</b> — {business_type}", body_style))
    story.append(Paragraph(f"Joylashuv: {location}", body_style))
    story.append(Paragraph(f"Tayyorlangan sana: {datetime.now().strftime('%d.%m.%Y')}", body_style))
    story.append(Spacer(1, 10))

    # --- Boshlang'ich xarajatlar ---
    story.append(Paragraph("1. Boshlang'ich xarajatlar", h2_style))
    cost_rows = [
        ["Xarajat turi", "Summasi"],
        ["Joy ijarasi (oylik)", _money(cost_estimate.get("rent_monthly", 0))],
        ["Remont", _money(cost_estimate.get("renovation_one_time", 0))],
        ["Jihozlar", _money(cost_estimate.get("equipment_one_time", 0))],
        ["Boshlang'ich mahsulotlar/tovar", _money(cost_estimate.get("initial_goods_one_time", 0))],
    ]
    for extra in cost_estimate.get("other_one_time_costs", []):
        cost_rows.append([extra.get("name", "Boshqa xarajat"), _money(extra.get("amount", 0))])
    cost_rows.append(["JAMI boshlang'ich xarajat", _money(cost_estimate.get("total_startup_cost", 0))])

    cost_table = Table(cost_rows, colWidths=[110 * mm, 50 * mm])
    cost_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a3a6b")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTSIZE", (0, 0), (-1, -1), 9.5),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cccccc")),
        ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#eef2fa")),
        ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(cost_table)
    story.append(Spacer(1, 10))

    # --- Moliyalashtirish manbai ---
    story.append(Paragraph("2. Moliyalashtirish manbai", h2_style))
    finance_rows = [
        ["Umumiy kerakli mablag'", _money(cost_estimate.get("total_startup_cost", 0))],
        ["Biznes egasining o'z mablag'i", _money(own_capital)],
        ["Kerakli kredit summasi", _money(loan_needed)],
    ]
    finance_table = Table(finance_rows, colWidths=[110 * mm, 50 * mm])
    finance_table.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cccccc")),
        ("FONTSIZE", (0, 0), (-1, -1), 9.5),
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#eef2fa")),
        ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(finance_table)
    story.append(Spacer(1, 10))

    # --- Oylik moliyaviy prognoz ---
    story.append(Paragraph("3. Oylik moliyaviy prognoz", h2_style))
    monthly_rows = [
        ["Ko'rsatkich", "Summasi"],
        ["Taxminiy oylik aylanma (daromad)", _money(cost_estimate.get("monthly_revenue_estimate", 0))],
        ["Taxminiy oylik xarajatlar", _money(cost_estimate.get("monthly_expenses_estimate", 0))],
        ["Taxminiy oylik soliq", _money(cost_estimate.get("monthly_tax_estimate", 0))],
        ["Taxminiy oylik sof foyda", _money(cost_estimate.get("monthly_net_profit_estimate", 0))],
    ]
    monthly_table = Table(monthly_rows, colWidths=[110 * mm, 50 * mm])
    monthly_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a3a6b")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cccccc")),
        ("FONTSIZE", (0, 0), (-1, -1), 9.5),
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(monthly_table)

    if cost_estimate.get("notes"):
        story.append(Spacer(1, 6))
        story.append(Paragraph(f"Izoh: {cost_estimate['notes']}", note_style))

    # --- Kredit to'lov jadvali ---
    if loan_schedules:
        story.append(PageBreak())
        story.append(Paragraph("4. Kredit to'lovlari jadvali", h2_style))
        summary_rows = [["Muddat", "Imtiyozli davr", "Imtiyozli davrdagi to'lov",
                          "Asosiy to'lov (annuitet)", "Jami to'langan foiz"]]
        for s in loan_schedules:
            summary_rows.append([
                f"{s.term_months} oy", f"{s.grace_months} oy",
                _money(s.monthly_payment_during_grace),
                _money(s.monthly_payment_after_grace),
                _money(s.total_interest_paid),
            ])
        summary_table = Table(summary_rows, colWidths=[22 * mm, 26 * mm, 38 * mm, 38 * mm, 36 * mm])
        summary_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a3a6b")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cccccc")),
            ("FONTSIZE", (0, 0), (-1, -1), 8.5),
            ("ALIGN", (1, 0), (-1, -1), "CENTER"),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ]))
        story.append(summary_table)
        story.append(Spacer(1, 6))
        story.append(Paragraph(
            "Eslatma: yuqoridagi foiz stavkasi va imtiyozli davr taxminiy ko'rsatilgan. "
            "Kreditni rasmiylashtirish oldidan tanlangan bankning aniq shartlarini so'rab oling.",
            note_style,
        ))

    doc.build(story)
    return filepath
