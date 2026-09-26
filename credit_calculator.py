"""
Kredit (ssuda) hisob-kitobi moduli.

Ishlaydigan model: annuitet to'lov + ixtiyoriy imtiyozli davr (grace period).
Imtiyozli davrda faqat foizlar to'lanadi, asosiy qarz (principal) o'sha davrda
kamaymaydi. Imtiyozli davr tugagach, qolgan muddat uchun standart annuitet
formulasi bo'yicha oylik to'lov hisoblanadi.

DIQQAT: DEFAULT_ANNUAL_INTEREST_RATE va DEFAULT_GRACE_PERIOD_MONTHS taxminiy
qiymatlar (config.py da). Aniq bank shartlari (foiz stavkasi, imtiyozli davr
muddati) bankdan-bankka farq qiladi — foydalanuvchiga buni eslatib turish kerak.
"""
from dataclasses import dataclass, field
from typing import List

from config import DEFAULT_ANNUAL_INTEREST_RATE, DEFAULT_GRACE_PERIOD_MONTHS


@dataclass
class MonthlyPaymentRow:
    month: int
    payment: float
    principal_part: float
    interest_part: float
    remaining_balance: float
    is_grace_period: bool


@dataclass
class LoanSchedule:
    principal: float
    annual_rate: float
    term_months: int
    grace_months: int
    monthly_payment_after_grace: float
    monthly_payment_during_grace: float
    total_interest_paid: float
    total_paid: float
    rows: List[MonthlyPaymentRow] = field(default_factory=list)


def calculate_schedule(
    principal: float,
    term_months: int,
    annual_rate: float = DEFAULT_ANNUAL_INTEREST_RATE,
    grace_months: int = DEFAULT_GRACE_PERIOD_MONTHS,
) -> LoanSchedule:
    """Berilgan summa, muddat va stavka bo'yicha to'liq to'lov jadvalini hisoblaydi."""
    if principal <= 0 or term_months <= 0:
        raise ValueError("Kredit summasi va muddati musbat bo'lishi kerak")

    grace_months = min(grace_months, max(term_months - 1, 0))  # butun muddat imtiyozli bo'lolmaydi
    monthly_rate = annual_rate / 100 / 12

    rows: List[MonthlyPaymentRow] = []
    balance = principal
    total_interest = 0.0

    # 1) Imtiyozli davr — faqat foiz to'lanadi
    grace_payment = round(balance * monthly_rate, 2) if grace_months > 0 else 0.0
    for m in range(1, grace_months + 1):
        interest = round(balance * monthly_rate, 2)
        rows.append(MonthlyPaymentRow(
            month=m, payment=interest, principal_part=0.0,
            interest_part=interest, remaining_balance=balance, is_grace_period=True,
        ))
        total_interest += interest

    # 2) Qolgan muddat — standart annuitet
    remaining_term = term_months - grace_months
    if monthly_rate > 0:
        annuity_payment = balance * (monthly_rate * (1 + monthly_rate) ** remaining_term) / (
            (1 + monthly_rate) ** remaining_term - 1
        )
    else:
        annuity_payment = balance / remaining_term
    annuity_payment = round(annuity_payment, 2)

    for i in range(1, remaining_term + 1):
        interest = round(balance * monthly_rate, 2)
        principal_part = round(annuity_payment - interest, 2)
        if i == remaining_term:
            principal_part = round(balance, 2)
            payment = round(principal_part + interest, 2)
        else:
            payment = annuity_payment
        balance = round(balance - principal_part, 2)
        total_interest += interest
        rows.append(MonthlyPaymentRow(
            month=grace_months + i, payment=payment, principal_part=principal_part,
            interest_part=interest, remaining_balance=max(balance, 0.0), is_grace_period=False,
        ))

    total_paid = round(principal + total_interest, 2)

    return LoanSchedule(
        principal=principal,
        annual_rate=annual_rate,
        term_months=term_months,
        grace_months=grace_months,
        monthly_payment_after_grace=annuity_payment,
        monthly_payment_during_grace=grace_payment,
        total_interest_paid=round(total_interest, 2),
        total_paid=total_paid,
        rows=rows,
    )


def compare_terms(
    principal: float,
    terms: List[int],
    annual_rate: float = DEFAULT_ANNUAL_INTEREST_RATE,
    grace_months: int = DEFAULT_GRACE_PERIOD_MONTHS,
) -> List[LoanSchedule]:
    """12/24/36/48 oy uchun bir vaqtda taqqoslash jadvalini qaytaradi."""
    return [calculate_schedule(principal, t, annual_rate, grace_months) for t in terms]


def format_comparison_message(schedules: List[LoanSchedule]) -> str:
    """Foydalanuvchiga Telegram xabari sifatida yuboriladigan taqqoslash matni."""
    lines = ["💳 <b>Kredit to'lovlari taqqoslash jadvali</b>\n"]
    for s in schedules:
        lines.append(
            f"📌 <b>{s.term_months} oy</b> muddat:\n"
            f"   • Imtiyozli davr: {s.grace_months} oy (oyiga faqat {s.monthly_payment_during_grace:,.0f} so'm foiz)\n"
            f"   • Imtiyozli davrdan keyingi oylik to'lov: <b>{s.monthly_payment_after_grace:,.0f} so'm</b>\n"
            f"   • Jami to'langan foiz: {s.total_interest_paid:,.0f} so'm\n"
            f"   • Jami to'lanadigan summa: {s.total_paid:,.0f} so'm\n"
        )
    lines.append(
        "\n⚠️ Stavka va imtiyozli davr taxminiy ko'rsatilgan — aniq shartlarni "
        "murojaat qilayotgan bankingizdan tasdiqlab oling."
    )
    return "\n".join(lines)
