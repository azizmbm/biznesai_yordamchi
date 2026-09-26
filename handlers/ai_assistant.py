from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from states import AiAssistantOnboarding, SubBotSetup
from keyboards import ai_assistant_hub_kb
from storage import Store
from ai_content import generate_bio, generate_smm_plan
from utils import safe_text

router = Router(name="ai_assistant")

NON_TEXT_PROMPT = (
    "Iltimos, javobingizni matn ko'rinishida yozing (rasm, stiker yoki ovozli "
    "xabar emas)."
)


# ---------------- Onboarding (birinchi marta) ----------------

@router.message(AiAssistantOnboarding.waiting_business_name_type, F.text)
async def get_name_type(message: Message, state: FSMContext) -> None:
    text = safe_text(message.text)
    if text is None:
        await message.answer(NON_TEXT_PROMPT)
        return
    await state.update_data(name_type=text)
    await state.set_state(AiAssistantOnboarding.waiting_since_and_branches)
    await message.answer(
        "2️⃣ Qachondan beri faoliyat yuritasiz va nechta filialingiz bor?\n"
        "Masalan: <i>2020 yil, 3 ta filial</i>"
    )


@router.message(AiAssistantOnboarding.waiting_since_and_branches, F.text)
async def get_since_branches(message: Message, state: FSMContext) -> None:
    text = safe_text(message.text)
    if text is None:
        await message.answer(NON_TEXT_PROMPT)
        return
    await state.update_data(since_and_branches=text)
    await state.set_state(AiAssistantOnboarding.waiting_advantages)
    await message.answer(
        "3️⃣ Biznesingizning raqobatchilardan ustunlik tomonlari qanday?\n"
        "Masalan: <i>Narx arzonligi, Qulay lokatsiya, Mahsulotlar Yevropadan keladi</i>"
    )


@router.message(AiAssistantOnboarding.waiting_advantages, F.text)
async def get_advantages(message: Message, state: FSMContext) -> None:
    text = safe_text(message.text)
    if text is None:
        await message.answer(NON_TEXT_PROMPT)
        return
    await state.update_data(advantages=text)
    await state.set_state(AiAssistantOnboarding.waiting_disadvantages)
    await message.answer(
        "4️⃣ Biznesingizning kamchilik tomonlari qanday?\n"
        "Masalan: <i>Dostavka pullik, Narx qimmatligi</i>"
    )


@router.message(AiAssistantOnboarding.waiting_disadvantages, F.text)
async def get_disadvantages(message: Message, state: FSMContext) -> None:
    text = safe_text(message.text)
    if text is None:
        await message.answer(NON_TEXT_PROMPT)
        return
    await state.update_data(disadvantages=text)
    await state.set_state(AiAssistantOnboarding.waiting_social_profile)
    await message.answer(
        "5️⃣ Ijtimoiy tarmoqlarda biznesingiz profili bormi? Va qancha umumiy "
        "obunachiga egasiz?\nMasalan: <i>Ha bor, 5300</i>"
    )


@router.message(AiAssistantOnboarding.waiting_social_profile, F.text)
async def get_social_profile(message: Message, state: FSMContext) -> None:
    text = safe_text(message.text)
    if text is None:
        await message.answer(NON_TEXT_PROMPT)
        return
    data = await state.get_data()
    profile = {
        "name_type": data["name_type"],
        "since_and_branches": data["since_and_branches"],
        "advantages": data["advantages"],
        "disadvantages": data["disadvantages"],
        "social_profile": text,
        "onboarded": True,
    }
    await Store.update_user(message.from_user.id, **profile)
    await state.clear()
    await message.answer(
        "✅ Rahmat! Biznesingiz haqida ma'lumotlarni saqladim.\n\n"
        "Endi quyidagi xizmatlardan foydalanishingiz mumkin:",
        reply_markup=ai_assistant_hub_kb(),
    )


# Onboarding bosqichlarida matn o'rniga boshqa turdagi xabar kelsa
@router.message(AiAssistantOnboarding.waiting_business_name_type)
@router.message(AiAssistantOnboarding.waiting_since_and_branches)
@router.message(AiAssistantOnboarding.waiting_advantages)
@router.message(AiAssistantOnboarding.waiting_disadvantages)
@router.message(AiAssistantOnboarding.waiting_social_profile)
async def onboarding_non_text(message: Message) -> None:
    await message.answer(NON_TEXT_PROMPT)


# ---------------- Asosiy AI-yordamchi menyusi ----------------

@router.callback_query(F.data == "ai:ig_bio")
async def on_ig_bio(callback: CallbackQuery) -> None:
    await callback.answer("Tayyorlanmoqda...")
    profile = await Store.get_user(callback.from_user.id)
    await callback.message.answer("⏳ Instagram bio yozilmoqda...")
    try:
        bio = await generate_bio("instagram", profile)
    except Exception as e:
        await callback.message.answer(f"❌ Xatolik: {e}")
        return
    await callback.message.answer(f"📝 <b>Instagram bio</b>:\n\n{bio}")


@router.callback_query(F.data == "ai:tg_bio")
async def on_tg_bio(callback: CallbackQuery) -> None:
    await callback.answer("Tayyorlanmoqda...")
    profile = await Store.get_user(callback.from_user.id)
    await callback.message.answer("⏳ Telegram bio yozilmoqda...")
    try:
        bio = await generate_bio("telegram", profile)
    except Exception as e:
        await callback.message.answer(f"❌ Xatolik: {e}")
        return
    await callback.message.answer(f"📝 <b>Telegram bio</b>:\n\n{bio}")


@router.callback_query(F.data == "ai:smm_plan")
async def on_smm_plan(callback: CallbackQuery) -> None:
    await callback.answer("Tayyorlanmoqda...")
    profile = await Store.get_user(callback.from_user.id)
    await callback.message.answer("⏳ 30 kunlik SMM-plan tuzilmoqda, bu biroz vaqt olishi mumkin...")
    try:
        plan = await generate_smm_plan(profile)
    except Exception as e:
        await callback.message.answer(f"❌ Xatolik: {e}")
        return

    await Store.update_user(callback.from_user.id, smm_plan=plan, smm_plan_day_index=0)

    day1 = plan[0]
    await callback.message.answer(
        f"📅 <b>30 kunlik SMM-plan tayyor!</b>\n\n"
        f"Har 24 soatda sizga navbatdagi kun uchun tayyor post matnlarini yuboraman.\n\n"
        f"<b>1-kun — 📸 Instagram</b> ({day1['instagram_idea']}):\n"
        f"{day1['instagram_script']}\n\n"
        f"<b>1-kun — ✈️ Telegram</b> ({day1['telegram_idea']}):\n"
        f"{day1['telegram_script']}"
    )


@router.callback_query(F.data == "ai:ai_seller")
async def on_ai_seller(callback: CallbackQuery, state: FSMContext) -> None:
    # Agar bu biznes egasi ilgari bot tokenini yuborib, "AI sotuvchi" botini
    # sozlab bo'lgan bo'lsa — tokenni qayta so'ramaymiz, to'g'ridan-to'g'ri
    # yangi mahsulot qo'shish bosqichiga o'tkazamiz.
    existing_token = await Store.get_subbot_token(callback.from_user.id)
    if existing_token:
        await state.set_state(SubBotSetup.waiting_product_name_price)
        await callback.message.answer(
            "🛒 <b>AI sotuvchi</b> botingiz allaqachon sozlangan!\n\n"
            "Keling, yangi mahsulot qo'shamiz.\n\n"
            "1️⃣ Mahsulotingiz nomi va narxini kiriting.\n"
            "Masalan: <i>Samsung 32 lik televizor, 2500000</i> yoki "
            "<i>Samsung 32 lik televizor, 2.5 mln</i>"
        )
        await callback.answer()
        return

    await state.set_state(SubBotSetup.waiting_token)
    await callback.message.answer(
        "🛒 <b>AI sotuvchi</b>ni sozlaymiz!\n\n"
        "1️⃣ @BotFather ga o'ting.\n"
        "2️⃣ <code>/newbot</code> buyrug'ini yuboring va bot uchun nom hamda "
        "username tanlang.\n"
        "3️⃣ BotFather sizga bot tokenini beradi — o'sha tokenni menga shu yerga "
        "yuboring.\n\n"
        "⚠️ Tokenni hech kim bilan baham ko'rmang — u faqat sizning botingizni "
        "boshqarish uchun ishlatiladi."
    )
    await callback.answer()
