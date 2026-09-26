from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.exceptions import TelegramUnauthorizedError
from aiogram.utils.token import TokenValidationError
import os

from states import SubBotSetup
from keyboards import product_has_photo_kb, add_more_products_kb, main_menu_kb
from storage import Store
from config import PRODUCT_PHOTOS_DIR
from utils import safe_text, parse_amount_uz
import subbot_manager

router = Router(name="subbot_products")


@router.message(SubBotSetup.waiting_token, F.text)
async def get_bot_token(message: Message, state: FSMContext) -> None:
    token = safe_text(message.text)
    if token is None:
        await message.answer("Iltimos, @BotFather dan olgan bot tokenini matn ko'rinishida yuboring.")
        return

    try:
        test_bot = Bot(token=token)
    except TokenValidationError:
        await message.answer(
            "❌ Bu token formati noto'g'ri ko'rinadi. @BotFather dan olgan tokenni "
            "(masalan: <code>123456:ABC-DEF...</code>) to'liq nusxalab yuboring."
        )
        return

    try:
        me = await test_bot.get_me()
    except TelegramUnauthorizedError:
        await message.answer("❌ Token noto'g'ri ko'rinadi. Iltimos, @BotFather dan olgan tokenni qaytadan yuboring.")
        return
    except Exception as e:
        await message.answer(f"❌ Tokenni tekshirishda xatolik yuz berdi. Birozdan so'ng qayta urinib ko'ring.\n(texnik tafsilot: {e})")
        return
    finally:
        await test_bot.session.close()

    await Store.register_subbot(message.from_user.id, token)
    await state.update_data(subbot_username=me.username)
    await state.set_state(SubBotSetup.waiting_product_name_price)
    await message.answer(
        f"✅ Bot topildi: @{me.username}\n\n"
        "Endi mahsulotlaringizni birma-bir kiritamiz.\n\n"
        "1️⃣ Mahsulotingiz nomi va narxini kiriting.\n"
        "Masalan: <i>Samsung 32 lik televizor, 2500000</i> yoki "
        "<i>Samsung 32 lik televizor, 2.5 mln</i>"
    )


@router.message(SubBotSetup.waiting_token)
async def get_bot_token_invalid(message: Message) -> None:
    await message.answer("Iltimos, @BotFather dan olgan bot tokenini matn ko'rinishida yuboring.")


def _split_name_price(text: str) -> tuple[str, float]:
    parts = text.rsplit(",", 1)
    if len(parts) == 2:
        price = parse_amount_uz(parts[1])
        if price:
            return parts[0].strip(), price
    return text.strip(), 0.0


@router.message(SubBotSetup.waiting_product_name_price, F.text)
async def get_product_name_price(message: Message, state: FSMContext) -> None:
    text = safe_text(message.text)
    if text is None:
        await message.answer(
            "Iltimos, mahsulot nomi va narxini matn ko'rinishida kiriting.\n"
            "Masalan: <i>Samsung 32 lik televizor, 2500000</i>"
        )
        return
    name, price = _split_name_price(text)
    if not name:
        await message.answer(
            "Mahsulot nomini aniqlay olmadim. Iltimos, <i>Nomi, Narxi</i> formatida yozing.\n"
            "Masalan: <i>Samsung 32 lik televizor, 2500000</i>"
        )
        return
    if price <= 0:
        await message.answer(
            f"«{name}» uchun narxni aniqlay olmadim. Iltimos, vergul bilan ajratib "
            "narxini ham kiriting.\nMasalan: <i>Samsung 32 lik televizor, 2500000</i>"
        )
        return
    await state.update_data(product_name=name, product_price=price)
    await state.set_state(SubBotSetup.waiting_has_photo_choice)
    await message.answer("2️⃣ Bu mahsulotingizning rasmi bormi?", reply_markup=product_has_photo_kb())


@router.message(SubBotSetup.waiting_product_name_price)
async def get_product_name_price_invalid(message: Message) -> None:
    await message.answer(
        "Iltimos, mahsulot nomi va narxini matn ko'rinishida kiriting.\n"
        "Masalan: <i>Samsung 32 lik televizor, 2500000</i>"
    )


@router.callback_query(SubBotSetup.waiting_has_photo_choice, F.data == "product_photo:yes")
async def ask_for_photo(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(SubBotSetup.waiting_product_photo)
    await callback.message.edit_text("📷 Mahsulot rasmini yuboring.")
    await callback.answer()


@router.message(SubBotSetup.waiting_product_photo, F.photo)
async def get_product_photo(message: Message, state: FSMContext, bot: Bot) -> None:
    # DIQQAT: file_id faqat shu (asosiy) botga tegishli — sub-bot boshqa token
    # bilan ishlagani uchun o'sha file_id orqali rasmni ochib bera olmaydi.
    # Shu sababli rasmni diskka yuklab olib, keyin sub-bot fayl sifatida yuboradi.
    os.makedirs(PRODUCT_PHOTOS_DIR, exist_ok=True)
    photo = message.photo[-1]
    local_path = os.path.join(PRODUCT_PHOTOS_DIR, f"{message.from_user.id}_{photo.file_unique_id}.jpg")
    await bot.download(photo, destination=local_path)
    await state.update_data(product_photo=local_path)
    await state.set_state(SubBotSetup.waiting_min_quantity)
    await message.answer("3️⃣ Mahsulotingizni kami bormi? (minimal narxni kiriting, aks holda 0 deb yozing)")


@router.callback_query(SubBotSetup.waiting_has_photo_choice, F.data == "product_photo:no")
async def no_photo(callback: CallbackQuery, state: FSMContext) -> None:
    await state.update_data(product_photo=None)
    await state.set_state(SubBotSetup.waiting_min_quantity)
    await callback.message.edit_text("3️⃣ Mahsulotingizni kami bormi? (minimal narxni kiriting, aks holda 0 deb yozing)")
    await callback.answer()


@router.message(SubBotSetup.waiting_product_photo)
async def get_product_photo_invalid(message: Message, state: FSMContext) -> None:
    """Foydalanuvchi rasm o'rniga boshqa narsa yuborsa (matn/stiker/hujjat va h.k.)."""
    if message.text and message.text.strip().lower() in ("yo'q", "yoq", "o'tkazib yubor", "skip"):
        await state.update_data(product_photo=None)
        await state.set_state(SubBotSetup.waiting_min_quantity)
        await message.answer(
            "Yaxshi, rasmsiz davom etamiz.\n\n"
            "3️⃣ Mahsulotingizni kami bormi? (minimal narxni kiriting, aks holda 0 deb yozing)"
        )
        return
    await message.answer(
        "Iltimos, mahsulot rasmini surat (photo) sifatida yuboring, yoki rasm yo'q "
        "bo'lsa \"yo'q\" deb yozing."
    )


@router.message(SubBotSetup.waiting_min_quantity, F.text)
async def get_min_price(message: Message, state: FSMContext) -> None:
    text = safe_text(message.text)
    data = await state.get_data()
    original_price = data.get("product_price", 0)

    min_price = 0.0
    if text and text.strip().lower() not in ("0", "yo'q", "yoq", "kerak emas", "-"):
        parsed = parse_amount_uz(text)
        if parsed is not None:
            min_price = parsed

    if min_price > original_price:
        await message.answer(
            f"⚠️ Minimal narx ({min_price:,.0f} so'm) asosiy narxdan ({original_price:,.0f} so'm) "
            "yuqori bo'lolmaydi. Iltimos, qaytadan kiriting yoki 0 deb yozing."
        )
        return

    product = {
        "name": data["product_name"],
        "original_price": original_price,
        "current_price": original_price,
        "min_price": min_price,
        "photo_path": data.get("product_photo"),
    }
    await Store.add_product(message.from_user.id, product)
    await state.clear()

    await message.answer(
        f"✅ <b>{product['name']}</b> saqlandi ({product['original_price']:,.0f} so'm).",
        reply_markup=add_more_products_kb(),
    )


@router.message(SubBotSetup.waiting_min_quantity)
async def get_min_price_invalid(message: Message) -> None:
    await message.answer("Iltimos, minimal narxni raqam bilan kiriting, aks holda 0 deb yozing.")


@router.callback_query(F.data == "product:add_more")
async def add_more_products(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(SubBotSetup.waiting_product_name_price)
    await callback.message.edit_text(
        "1️⃣ Mahsulotingiz nomi va narxini kiriting.\nMasalan: <i>Samsung 32 lik televizor, 2500000</i>"
    )
    await callback.answer()


@router.callback_query(F.data == "product:back_to_menu")
async def back_to_menu(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    products = await Store.get_products(callback.from_user.id)
    if products:
        await subbot_manager.ensure_subbot_running(callback.from_user.id)
        await callback.message.edit_text(
            "🎉 AI sotuvchi botingiz ishga tushdi! Mijozlar endi sizning botingiz "
            "orqali xarid qilishlari mumkin."
        )
    else:
        await callback.message.edit_text("Bosh menyu:", reply_markup=main_menu_kb())
    await callback.answer()
