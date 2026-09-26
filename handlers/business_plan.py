from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, FSInputFile
from aiogram.fsm.context import FSMContext

from states import BusinessPlanFlow
from keyboards import loan_term_kb
from ai_content import estimate_business_costs
from credit_calculator import calculate_schedule, compare_terms, format_comparison_message
from pdf_generator import build_business_plan_pdf
from config import LOAN_TERMS_MONTHS
from utils import safe_text, parse_amount_uz

router = Router(name="business_plan")

NON_TEXT_PROMPT = "Iltimos, javobingizni matn ko'rinishida yozing."


@router.message(BusinessPlanFlow.waiting_business_name, F.text)
async def get_business_name(message: Message, state: FSMContext) -> None:
    text = safe_text(message.text)
    if text is None:
        await message.answer(NON_TEXT_PROMPT)
        return
    await state.update_data(business_name_type=text)
    await state.set_state(BusinessPlanFlow.waiting_location)
    await message.answer(
        "2️⃣ Endi biznesingiz joylashadigan shahar va manzilni kiriting.\n"
        "Masalan: <i>Toshkent, Chilonzor tumani</i>"
    )


@router.message(BusinessPlanFlow.waiting_business_name)
async def get_business_name_invalid(message: Message) -> None:
    await message.answer(NON_TEXT_PROMPT)


@router.message(BusinessPlanFlow.waiting_location, F.text)
async def get_location(message: Message, state: FSMContext) -> None:
    text = safe_text(message.text)
    if text is None:
        await message.answer(NON_TEXT_PROMPT)
        return
    await state.update_data(location=text)
    await state.set_state(BusinessPlanFlow.waiting_own_capital)
    await message.answer(
        "3️⃣ Hozirda o'zingizda qancha mablag' bor? (so'mda)\n"
        "Masalan: <i>30000000</i> yoki <i>30 mln</i>"
    )


@router.message(BusinessPlanFlow.waiting_location)
async def get_location_invalid(message: Message) -> None:
    await message.answer(NON_TEXT_PROMPT)


@router.message(BusinessPlanFlow.waiting_own_capital, F.text)
async def get_own_capital(message: Message, state: FSMContext) -> None:
    text = safe_text(message.text)
    own_capital = parse_amount_uz(text)
    if own_capital is None:
        await message.answer(
            "Summani tushunolmadim. Iltimos, raqam bilan kiriting.\n"
            "Masalan: <i>30000000</i> yoki <i>30 mln</i>"
        )
        return
    await state.update_data(own_capital=own_capital)
    await state.set_state(BusinessPlanFlow.calculating)

    wait_msg = await message.answer("⏳ Ma'lumotlaringiz asosida hisob-kitob qilinmoqda, biroz kuting...")

    data = await state.get_data()
    business_name_type = data["business_name_type"]
    location = data["location"]

    # Nomi va turini ajratib olishga urinamiz ("Salvador kiyim do'koni" -> nomi, turi)
    parts = business_name_type.split(" ", 1)
    business_name = parts[0]
    business_type = parts[1] if len(parts) > 1 else business_name_type

    try:
        cost_estimate = await estimate_business_costs(
            business_name=business_name,
            business_type=business_type,
            city=location,
            district=None,
            own_capital=own_capital,
        )
    except Exception as e:
        await wait_msg.edit_text(
            "❌ Hisob-kitob qilishda xatolik yuz berdi. Birozdan so'ng qayta urinib ko'ring.\n"
            f"(texnik tafsilot: {e})"
        )
        await state.clear()
        return

    total_startup_cost = float(cost_estimate.get("total_startup_cost", 0))
    loan_needed = max(total_startup_cost - own_capital, 0)

    await state.update_data(
        cost_estimate=cost_estimate,
        loan_needed=loan_needed,
        business_name=business_name,
        business_type=business_type,
    )

    summary = (
        f"✅ <b>Hisob-kitob tayyor!</b>\n\n"
        f"🏢 Biznes: {business_name_type}\n"
        f"📍 Manzil: {location}\n\n"
        f"💰 <b>Boshlang'ich xarajatlar:</b>\n"
        f"   • Ijara (oylik): {cost_estimate.get('rent_monthly', 0):,.0f} so'm\n"
        f"   • Remont: {cost_estimate.get('renovation_one_time', 0):,.0f} so'm\n"
        f"   • Jihozlar: {cost_estimate.get('equipment_one_time', 0):,.0f} so'm\n"
        f"   • Boshlang'ich tovar: {cost_estimate.get('initial_goods_one_time', 0):,.0f} so'm\n"
        f"   • <b>Jami kerakli mablag': {total_startup_cost:,.0f} so'm</b>\n\n"
        f"📊 <b>Oylik prognoz:</b>\n"
        f"   • Aylanma: {cost_estimate.get('monthly_revenue_estimate', 0):,.0f} so'm\n"
        f"   • Xarajatlar: {cost_estimate.get('monthly_expenses_estimate', 0):,.0f} so'm\n"
        f"   • Soliq: {cost_estimate.get('monthly_tax_estimate', 0):,.0f} so'm\n"
        f"   • Sof foyda: {cost_estimate.get('monthly_net_profit_estimate', 0):,.0f} so'm\n\n"
        f"🏦 <b>Sizning mablag'ingiz:</b> {own_capital:,.0f} so'm\n"
    )

    if loan_needed > 0:
        summary += f"💳 <b>Kerakli kredit summasi:</b> {loan_needed:,.0f} so'm\n\n" \
                    "Quyidan kredit muddatini tanlang — oylik to'lovlarni ko'rsataman:"
        await wait_msg.edit_text(summary)
        await message.answer("Kredit muddatini tanlang:", reply_markup=loan_term_kb())
        await state.set_state(BusinessPlanFlow.waiting_loan_term_choice)
    else:
        summary += "\n🎉 O'z mablag'ingiz boshlang'ich xarajatni to'liq qoplaydi — kredit shart emas!"
        await wait_msg.edit_text(summary)
        pdf_path = build_business_plan_pdf(
            business_name=business_name, business_type=business_type, location=location,
            own_capital=own_capital, cost_estimate=cost_estimate, loan_needed=0, loan_schedules=[],
        )
        await message.answer_document(FSInputFile(pdf_path), caption="📄 Biznes-rejangiz PDF holida tayyor.")
        await state.clear()


@router.message(BusinessPlanFlow.waiting_own_capital)
async def get_own_capital_invalid(message: Message) -> None:
    await message.answer(
        "Iltimos, mablag' miqdorini raqam bilan yozing.\nMasalan: <i>30000000</i> yoki <i>30 mln</i>"
    )


@router.callback_query(BusinessPlanFlow.waiting_loan_term_choice, F.data.startswith("loan_term:"))
async def on_loan_term_choice(callback: CallbackQuery, state: FSMContext) -> None:
    choice = callback.data.split(":", 1)[1]
    data = await state.get_data()
    loan_needed = data["loan_needed"]

    if choice == "all":
        schedules = compare_terms(loan_needed, LOAN_TERMS_MONTHS)
    else:
        schedules = [calculate_schedule(loan_needed, int(choice))]

    await callback.message.edit_text(format_comparison_message(schedules))

    pdf_path = build_business_plan_pdf(
        business_name=data["business_name"], business_type=data["business_type"],
        location=data["location"], own_capital=data["own_capital"],
        cost_estimate=data["cost_estimate"], loan_needed=loan_needed, loan_schedules=schedules,
    )
    await callback.message.answer_document(
        FSInputFile(pdf_path), caption="📄 Bankka topshirish uchun tayyor biznes-reja."
    )
    await state.clear()
    await callback.answer()
