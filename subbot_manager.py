"""
Har bir biznes egasi uchun alohida "AI sotuvchi" sub-botini dinamik tarzda
ishga tushiruvchi modul.

Yondashuv: har bir sub-bot uchun alohida aiogram Bot/Dispatcher yaratiladi va
asyncio background task sifatida long-polling rejimida ishga tushiriladi.
Bir nechta sub-bot bitta process ichida parallel ishlaydi.

Katta miqyosda (yuzlab sub-botlar) ishlatish uchun webhook + bitta ASGI server
orqali multiplekslash ancha samarali bo'ladi — bu yerda soddalik uchun polling
tanlandi.

--- Optimallashtirish tarixi ---
Quyidagi haqiqiy foydalanuvchi test-sessiyasida topilgan xatoliklar tuzatildi:
  1) Mijoz manzilni matn o'rniga Telegram "location" (joylashuv) sifatida
     yuborsa, `message.text` None bo'lib, bot AttributeError bilan yiqilardi.
     -> Endi location alohida qabul qilinadi.
  2) Mijoz narxni harflar bilan ("3,6 mln") yoki mahsulot nomini to'liq
     yozmasdan so'rasa, bot buni tushunmasdi.
     -> `utils.parse_amount_uz` va so'zlar bo'yicha moslashtiruvchi
        `_find_product` qo'shildi.
  3) Mijoz kelishilgan narxdan keyin tugmani bosmasdan, oddiy matn bilan
     ("ha, olaman" kabi) tasdiqlasa, bot buni sotib olish sifatida
     qabul qilmasdi.
     -> Oxirgi taklif qilingan mahsulot FSM state-data’sida saqlanadi va
        tasdiqlovchi so'zlar aniqlanadi.
  4) "⬅️ Ortga" tugmasi ("buy:back") uchun umuman handler yo'q edi — bosilganda
     bot hech narsa qilmas, so'rov "osilib" qolardi.
     -> Handler qo'shildi.
  5) Har qanday matn kutilgan bosqichda mijoz rasm/ovozli xabar/stiker yuborsa
     bot yiqilishi yoki jim qolishi mumkin edi.
     -> Barcha bosqichlarda xavfsiz fallback javoblar qo'shildi.
  6) [KRITIK] Bitta mijoz bilan savdolashib biror narxga kelishilganda, bot
     bu narxni `products.json`dagi UMUMIY `current_price`ga yozib qo'yardi —
     natijada boshqa barcha mijozlar ham /start bosganda o'sha (chegirmali)
     narxni ko'rar edi.
     -> Kelishilgan narx endi umumiy mahsulot yozuviga emas, faqat SHU
        mijozning o'z yozuvidagi `negotiated_prices`ga saqlanadi
        (`storage.py: get/set_negotiated_price`) va faqat o'sha mijozga
        ko'rsatiladi.
  7) Savdolashuv qat'iy qoidalar (kalit so'zlar) asosida ishlar va odatda
     1-2 xabardan keyin "tugab qolar", undan keyingi taklif/savolga mahsulot
     bo'yicha kontekstga mos javob bermas edi.
     -> Butun erkin matnli suhbat endi `ai_content.negotiate_reply` orqali
        Claude'ga yuboriladi — u har safar mijoz bilan bo'lgan OLDINGI
        SUHBAT TARIXINI (`Store.get_customer_chat_history`) va mijoz
        haqida ma'lum afzalliklarni (`Store.get_customer_preferences`)
        hisobga olib javob beradi, shuning uchun savdolashuv sun'iy
        ravishda to'xtab qolmaydi.
  8) [KRITIK] Mijoz bir nechta xil mahsulot sotib olmoqchi bo'lsa ham, bot
     faqat OXIRGI tanlangan mahsulotni buyurtma sifatida qabul qilib,
     sotuvchiga faqat o'shani yuborardi — oldingi tanlovlar "yo'qolib"
     ketardi (bitta so'ralgan "upsell" mahsulotidan tashqari boshqasini
     qo'sha olmasdi).
     -> Endi to'liq SAVATCHA (cart) mantig'i qo'shildi: har bir tanlangan
        mahsulot + miqdor FSM state-data'dagi `cart` ro'yxatiga qo'shiladi
        (`_add_current_item_to_cart`). Mahsulot qo'shilgandan keyin mijozga
        "🛍 Yana mahsulot qo'shish" / "✅ Buyurtmani rasmiylashtirish"
        tugmalari ko'rsatiladi (`cart_action_kb`) — xohlagancha mahsulot
        qo'shishi mumkin. Faqat "Buyurtmani rasmiylashtirish" bosilgandagina
        `_finalize_order` savatdagi BARCHA mahsulotlarni (nomi, soni, narxi,
        jami summa) bitta buyurtma sifatida sotuvchiga yuboradi.
"""
import asyncio
import logging
import os
import re
from typing import Dict, Optional, Tuple

from aiogram import Bot, Dispatcher, Router, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Message, CallbackQuery, FSInputFile

from keyboards import buy_confirm_kb, cart_action_kb
from states import CustomerOrderFlow
from storage import Store
from ai_content import negotiate_reply
from utils import safe_text, parse_quantity, looks_like_phone

logger = logging.getLogger(__name__)

_running_subbots: Dict[int, asyncio.Task] = {}
_main_bot: Optional[Bot] = None

MAX_REASONABLE_QUANTITY = 100

# ---------------- Mijoz xabarlarini tushunish uchun kalit so'zlar ----------------
# ENDI faqat "ha"/"yo'q" kabi ikkilanmas tugmasiz javoblarni tez aniqlash uchun
# ishlatiladi (pastga qarang). Narx savdolashuvi, yetkazib berish/to'lov/kafolat
# kabi erkin savol-javoblar endi AI (ai_content.negotiate_reply) orqali hal
# qilinadi — shu sababli eski DELIVERY_WORDS/PAYMENT_WORDS/... ro'yxatlari va
# qat'iy 2 xabardan keyin tugaydigan savdolashuv mantiqi olib tashlandi.
#
# "ha", "ok" kabi juda qisqa so'zlar boshqa so'zlar ichida ham uchrashi mumkin
# (masalan "ha" — "rahmat" so'zining ichida bor). Shu sababli bular alohida
# TO'LIQ SO'Z (token) sifatida tekshiriladi, substring emas — aks holda
# "rahmat" yoki "necha pulga bo'ladimi?" kabi xabarlar xato ravishda
# "tasdiqlash" deb qabul qilinib qolardi.
AFFIRMATIVE_EXACT_WORDS = {
    "ha", "mayli", "roziman", "rozi", "olaman", "beraman", "xop", "yaxshi",
    "ok", "okay", "oldim",
}
AFFIRMATIVE_PHRASES = ("olib qol", "sotib olaman", "olib qolaman", "buyurtma beraman")
NEGATIVE_EXACT_WORDS = {"yoq", "bekor"}
NEGATIVE_PHRASES = ("kerak emas", "hozir emas")


def _normalize_apostrophes(text_lower: str) -> str:
    return text_lower.replace("'", "").replace("ʻ", "").replace("’", "").replace("`", "")


def _tokens(text_lower: str):
    return re.findall(r"[a-z0-9]+", _normalize_apostrophes(text_lower))


def _is_affirmative(text_lower: str) -> bool:
    if any(p in text_lower for p in AFFIRMATIVE_PHRASES):
        return True
    return any(tok in AFFIRMATIVE_EXACT_WORDS for tok in _tokens(text_lower))


def _is_negative(text_lower: str) -> bool:
    if any(p in text_lower for p in NEGATIVE_PHRASES):
        return True
    return any(tok in NEGATIVE_EXACT_WORDS for tok in _tokens(text_lower))


def set_main_bot(bot: Bot) -> None:
    """bot.py orqali chaqiriladi — buyurtma bildirishnomalarini yuborish uchun kerak."""
    global _main_bot
    _main_bot = bot


def _find_product_by_text(products: Dict[str, dict], text_lower: str) -> Optional[Tuple[str, dict]]:
    """
    Mijoz matnida mahsulot nomiga oid so'zlarni qidiradi va eng ko'p mos
    kelgan mahsulotni qaytaradi (mijoz to'liq nom yozmasa ham ishlaydi,
    masalan "kir yuvish mashinasi" o'rniga shunchaki "mashina" yozilsa ham —
    o'zbek tilida ko'p uchraydigan qo'shimchali shakllarni (mashina/mashinasi)
    hisobga olish uchun so'z boshi bo'yicha ham solishtiriladi).
    Do'konda bitta mahsulot bo'lsa va matn xaridga oid ko'rinsa, shuni qaytaradi.
    """
    text_tokens = [t for t in re.split(r"\W+", text_lower) if len(t) >= 4]
    best_match: Optional[Tuple[str, dict]] = None
    best_score = 0
    for product_id, product in products.items():
        words = [w for w in re.split(r"\W+", product["name"].lower()) if len(w) >= 3]
        score = 0
        for w in words:
            if w in text_lower:
                score += 1
            elif len(w) >= 4 and any(w[:4] == t[:4] for t in text_tokens):
                score += 1
        if score > best_score:
            best_score = score
            best_match = (product_id, product)
    if best_match:
        return best_match
    if len(products) == 1:
        return next(iter(products.items()))
    return None


def _add_current_item_to_cart(data: dict) -> list:
    """Joriy tanlangan mahsulot + miqdorni savatga qo'shadi va yangilangan
    savat ro'yxatini qaytaradi (state.update_data bilan saqlash uchun)."""
    cart = list(data.get("cart", []))
    cart.append({
        "product_id": data["product_id"],
        "name": data["product_name"],
        "price": data["product_price"],
        "quantity": data["quantity"],
    })
    return cart


def _cart_summary_text(cart: list) -> str:
    lines = ["🛍 <b>Savatingizga qo'shildi!</b>\n", "Hozirgi savat:"]
    total = 0.0
    for item in cart:
        subtotal = item["price"] * item["quantity"]
        total += subtotal
        lines.append(f"• {item['name']} x{item['quantity']} — {subtotal:,.0f} so'm")
    lines.append(f"\n💰 <b>Jami: {total:,.0f} so'm</b>")
    return "\n".join(lines)

def _build_customer_router(owner_id: int) -> Router:
    router = Router(name=f"subbot_customer_{owner_id}")

    async def _show_products(target: Message, customer_tg_id: Optional[int] = None) -> None:
        products = await Store.get_products(owner_id)
        if not products:
            await target.answer("Kechirasiz, hozircha mahsulotlar mavjud emas.")
            return
        for product_id, product in products.items():
            # DIQQAT (narx bug'i tuzatildi): oldin savdolashib kelishilgan narx
            # `products.json`dagi umumiy `current_price`ga yozilardi — shu
            # sababli bitta mijoz bilan kelishilgan chegirma BOSHQA BARCHA
            # mijozlarga ham ko'rsatilib qolardi. Endi bunday shaxsiy narx
            # faqat shu mijozning o'z yozuvida saqlanadi va faqat SHU mijozga
            # ko'rsatiladi — boshqa mijozlar har doim asosiy narxni ko'radi.
            display_price = product["current_price"]
            if customer_tg_id is not None:
                negotiated = await Store.get_negotiated_price(owner_id, customer_tg_id, product_id)
                if negotiated:
                    display_price = negotiated
            caption = (
                f"<b>{product['name']}</b>\n"
                f"💰 Narxi: {display_price:,.0f} so'm"
            )
            photo_path = product.get("photo_path")
            if photo_path and os.path.exists(photo_path):
                await target.answer_photo(
                    FSInputFile(photo_path), caption=caption,
                    reply_markup=buy_confirm_kb(product_id),
                )
            else:
                await target.answer(caption, reply_markup=buy_confirm_kb(product_id))

    @router.message(CommandStart())
    async def customer_start(message: Message, state: FSMContext) -> None:
        await state.clear()
        products = await Store.get_products(owner_id)
        if not products:
            await message.answer("Kechirasiz, hozircha mahsulotlar mavjud emas.")
            return
        await message.answer(
            "Assalomu Alaykum, botimizga xush kelibsiz! 🛍\n\n"
            "Quyidagi mahsulotlardan qaysi biri sizga ma'qul? Bemalol mendan "
            "mahsulot narxi haqida savollaringizga javob olishingiz yoki "
            "mahsulotlarga buyurtma berishingiz mumkin!"
        )
        await _show_products(message, customer_tg_id=message.chat.id)

    async def _start_purchase(message: Message, state: FSMContext, product_id: str) -> None:
        products = await Store.get_products(owner_id)
        product = products.get(product_id)
        if not product:
            await message.answer("Kechirasiz, bu mahsulot topilmadi. /start bosib qayta ko'ring.")
            return
        # Agar shu mijoz bilan AI oldinroq boshqa narxga kelishgan bo'lsa — o'sha
        # (faqat shu mijozga xos) narxni ishlatamiz, umumiy narxni emas.
        negotiated = await Store.get_negotiated_price(owner_id, message.chat.id, product_id)
        price = negotiated if negotiated else product["current_price"]
        await state.update_data(product_id=product_id, product_name=product["name"],
                                 product_price=price)
        await state.set_state(CustomerOrderFlow.waiting_quantity)
        await message.answer("Nechta sotib olmoqchisiz?")

    def _ambiguous_product_prompt(products: Dict[str, dict]) -> str:
        names = ", ".join(f"«{p['name']}»" for p in products.values())
        return f"Qaysi mahsulot haqida so'rayapsiz? Mavjud mahsulotlar: {names}"

    @router.message(StateFilter(None), F.text)
    async def customer_free_text(message: Message, state: FSMContext) -> None:
        text = safe_text(message.text) or ""
        text_lower = text.lower()
        customer_tg_id = message.chat.id
        products = await Store.get_products(owner_id)
        if not products:
            await message.answer("Kechirasiz, hozircha mahsulotlar mavjud emas.")
            return
        data = await state.get_data()

        # 1) Avval taklif qilingan mahsulotga tugmasiz, oddiy "ha"/"yo'q" bilan
        # javob berilyaptimi? (Bu — tez, AI'ga murojaat qilmasdan hal
        # qilinadigan yagona holat, chunki bu yerda ikkilanish yo'q.)
        last_offer_id = data.get("last_offer_product_id")
        if last_offer_id and last_offer_id in products:
            if _is_negative(text_lower):
                await message.answer(
                    "Yaxshi, xohlasangiz keyinroq qaytib kelishingiz mumkin. "
                    "/start bosib mahsulotlar ro'yxatini qayta ko'ring."
                )
                return
            if _is_affirmative(text_lower):
                await _start_purchase(message, state, last_offer_id)
                return

        # 2) Suhbat qaysi mahsulot haqida ketayotganini aniqlaymiz: avval shu
        # mijoz bilan hozir muhokama qilinayotgan mahsulot (agar bo'lsa),
        # bo'lmasa — matn ichidan mos mahsulotni topishga harakat qilamiz.
        product_id = data.get("current_product_id")
        if product_id not in products:
            match = _find_product_by_text(products, text_lower)
            if match:
                product_id = match[0]
            elif len(products) == 1:
                product_id = next(iter(products))
            else:
                await message.answer(_ambiguous_product_prompt(products))
                return

        product = dict(products[product_id])
        # DIQQAT (narx bug'i tuzatildi): agar shu mijoz bilan oldin boshqa
        # narxga kelishilgan bo'lsa, faqat SHU mijoz uchun saqlangan narxni
        # ishlatamiz — umumiy `products.json`dagi narx o'zgarmaydi va boshqa
        # mijozlarga ta'sir qilmaydi.
        negotiated = await Store.get_negotiated_price(owner_id, customer_tg_id, product_id)
        if negotiated:
            product["current_price"] = negotiated

        # 3) AI sotuvchiga murojaat: butun oldingi suhbat tarixi va mijoz
        # haqida ma'lum afzalliklar asosida javob yaratadi. Shu tufayli
        # savdolashuv 1-2 xabardan keyin sun'iy to'xtamaydi — model har
        # safar kontekstni ko'rib javob beradi.
        await Store.append_customer_message(owner_id, customer_tg_id, "customer", text)
        history = await Store.get_customer_chat_history(owner_id, customer_tg_id)
        preferences = await Store.get_customer_preferences(owner_id, customer_tg_id)

        result = await negotiate_reply(product, text, history, preferences)

        reply_text = result["reply"]
        await Store.append_customer_message(owner_id, customer_tg_id, "bot", reply_text)
        await state.update_data(current_product_id=product_id, last_offer_product_id=product_id)

        if result.get("preference_note"):
            await Store.add_customer_preference(owner_id, customer_tg_id, result["preference_note"])

        kb = None
        agreed_price = result.get("agreed_price")
        if agreed_price:
            # Faqat SHU mijozning yozuviga saqlanadi — boshqa mijozlarning
            # ko'rgan narxi o'zgarmaydi.
            await Store.set_negotiated_price(owner_id, customer_tg_id, product_id, agreed_price)
            kb = buy_confirm_kb(product_id)

        await message.answer(reply_text, reply_markup=kb)

    @router.message(StateFilter(None), ~F.text)
    async def customer_non_text(message: Message) -> None:
        """Mijoz matn o'rniga rasm/ovozli xabar/stiker yuborsa bot yiqilmasligi uchun."""
        await message.answer(
            "Kechirasiz, buni tushunmadim. 🙂 Savolingizni matn ko'rinishida yozing "
            "yoki /start bosib mahsulotlar ro'yxatini ko'ring."
        )

    @router.callback_query(StateFilter(None), F.data == "buy:back")
    async def back_to_products(callback: CallbackQuery, state: FSMContext) -> None:
        # DIQQAT: oldin bu yerda `state.clear()` chaqirilardi — bu mijozning
        # hali rasmiylashtirilmagan SAVATINI ham o'chirib yuborardi. Endi
        # faqat joriy tanlangan mahsulot tozalanadi, savat saqlanib qoladi.
        await state.update_data(current_product_id=None, last_offer_product_id=None)
        await _show_products(callback.message, customer_tg_id=callback.from_user.id)
        await callback.answer()

    @router.callback_query(F.data.startswith("buy:") & F.data.contains(":yes"))
    async def confirm_purchase(callback: CallbackQuery, state: FSMContext) -> None:
        product_id = callback.data.split(":")[1]
        await _start_purchase(callback.message, state, product_id)
        await callback.answer()

    @router.message(CustomerOrderFlow.waiting_quantity)
    async def get_quantity(message: Message, state: FSMContext) -> None:
        quantity = parse_quantity(message.text, default=1)
        quantity = max(1, min(quantity, MAX_REASONABLE_QUANTITY))
        await state.update_data(quantity=quantity)

        data = await state.get_data()
        cart = _add_current_item_to_cart(data)
        await state.update_data(cart=cart)
        # Savatga qo'shilgach, mijoz erkin xabar yozib davom eta olishi
        # (masalan yana savdolashish) uchun holatni bo'shatamiz — tugmalar
        # orqali ham "yana qo'shish"/"yakunlash" tanlay oladi.
        await state.set_state(None)

        await message.answer(_cart_summary_text(cart), reply_markup=cart_action_kb())

    @router.callback_query(F.data == "cart:add_more")
    async def cart_add_more(callback: CallbackQuery, state: FSMContext) -> None:
        # Savatni saqlab qolamiz, faqat joriy tanlangan mahsulotni tozalaymiz —
        # shunda mijoz yangi mahsulot tanlashi mumkin.
        await state.update_data(current_product_id=None, last_offer_product_id=None)
        await _show_products(callback.message, customer_tg_id=callback.from_user.id)
        await callback.answer()

    @router.callback_query(F.data == "cart:checkout")
    async def cart_checkout(callback: CallbackQuery, state: FSMContext) -> None:
        data = await state.get_data()
        if not data.get("cart"):
            await callback.answer("Savatingiz bo'sh.", show_alert=True)
            return
        await _proceed_to_customer_details(callback.message, state)
        await callback.answer()

    async def _proceed_to_customer_details(message: Message, state: FSMContext) -> None:
        customer = await Store.get_customer(owner_id, message.chat.id)
        if customer.get("name") and customer.get("phone"):
            await state.update_data(customer_name=customer["name"], customer_phone=customer["phone"])
            await state.set_state(CustomerOrderFlow.waiting_customer_address)
            await message.answer(
                "Buyurtmani yetkazish uchun manzilingizni yozing, yoki 📎 tugmasi "
                "orqali joylashuvingizni (location) yuborishingiz ham mumkin."
            )
        else:
            await state.set_state(CustomerOrderFlow.waiting_customer_name_phone)
            await message.answer(
                "Ismingizni va telefon raqamingizni kiriting (masalan: Aziz, "
                "+998901234567), yoki 📎 orqali kontaktingizni ulashing."
            )

    @router.message(CustomerOrderFlow.waiting_customer_name_phone, F.contact)
    async def get_customer_details_contact(message: Message, state: FSMContext) -> None:
        contact = message.contact
        name = contact.first_name or (message.from_user.full_name if message.from_user else "Mijoz")
        phone = contact.phone_number or "kiritilmagan"
        await Store.save_customer(owner_id, message.chat.id, name, phone)
        await state.update_data(customer_name=name, customer_phone=phone)
        await state.set_state(CustomerOrderFlow.waiting_customer_address)
        await message.answer("Rahmat! Endi buyurtmani yetkazish uchun manzilingizni yuboring.")

    @router.message(CustomerOrderFlow.waiting_customer_name_phone, F.text)
    async def get_customer_details(message: Message, state: FSMContext) -> None:
        text = safe_text(message.text)
        if text is None:
            await message.answer(
                "Iltimos, ismingiz va telefon raqamingizni matn ko'rinishida yuboring "
                "(masalan: Aziz, +998901234567)."
            )
            return
        if "," in text:
            name_part, phone_part = text.split(",", 1)
            name = name_part.strip() or "Mijoz"
            phone = phone_part.strip() or "kiritilmagan"
        else:
            # Vergulsiz yozilgan bo'lsa ("Aziz +998901234567") — telefonga
            # o'xshagan so'zni ajratib olamiz, aks holda hammasini ism deb olamiz.
            tokens = text.split()
            phone_token = next((t for t in reversed(tokens) if looks_like_phone(t)), None)
            if phone_token:
                name = text.replace(phone_token, "").strip() or "Mijoz"
                phone = phone_token
            else:
                name, phone = text, "kiritilmagan"
        await Store.save_customer(owner_id, message.chat.id, name, phone)
        await state.update_data(customer_name=name, customer_phone=phone)
        await state.set_state(CustomerOrderFlow.waiting_customer_address)
        await message.answer("Rahmat! Endi buyurtmani yetkazish uchun manzilingizni yuboring.")

    @router.message(CustomerOrderFlow.waiting_customer_name_phone)
    async def get_customer_details_invalid(message: Message) -> None:
        await message.answer(
            "Iltimos, ismingiz va telefon raqamingizni matn ko'rinishida yozing "
            "(masalan: Aziz, +998901234567), yoki 📎 orqali kontakt ulashing."
        )

    @router.message(CustomerOrderFlow.waiting_customer_address, F.location)
    async def get_customer_location(message: Message, state: FSMContext) -> None:
        lat, lon = message.location.latitude, message.location.longitude
        address = f"📍 Joylashuv (xarita): https://maps.google.com/?q={lat},{lon}"
        await _finalize_order(message, state, address)

    @router.message(CustomerOrderFlow.waiting_customer_address, F.text)
    async def get_customer_address(message: Message, state: FSMContext) -> None:
        address = safe_text(message.text)
        if address is None:
            await message.answer(
                "Iltimos, manzilingizni matn ko'rinishida yozing, yoki 📎 orqali "
                "joylashuvingizni (location) yuboring."
            )
            return
        await _finalize_order(message, state, address)

    @router.message(CustomerOrderFlow.waiting_customer_address)
    async def get_customer_address_invalid(message: Message) -> None:
        await message.answer(
            "Iltimos, manzilingizni matn ko'rinishida yozing, yoki 📎 orqali "
            "joylashuvingizni (location) yuboring."
        )

    async def _finalize_order(message: Message, state: FSMContext, address: str) -> None:
        data = await state.get_data()
        cart = data.get("cart", [])

        order_lines = ["🆕 <b>Yangi buyurtma!</b>\n"]
        total = 0.0
        for item in cart:
            subtotal = item["price"] * item["quantity"]
            total += subtotal
            order_lines.append(f"📦 {item['name']} x{item['quantity']} — {subtotal:,.0f} so'm")
        order_lines.append(f"\n💰 <b>Jami: {total:,.0f} so'm</b>")
        order_lines.append(
            f"\n👤 Mijoz: {data.get('customer_name', 'Nomaʼlum')}\n"
            f"📞 Telefon: {data.get('customer_phone', 'kiritilmagan')}\n"
            f"📍 Manzil: {address}\n"
        )
        order_text = "\n".join(order_lines)

        if _main_bot is not None:
            try:
                await _main_bot.send_message(owner_id, order_text)
            except Exception:
                logger.exception("Buyurtma haqida biznes egasiga xabar yuborib bo'lmadi")

        await message.answer("✅ Buyurtmangiz qabul qilindi! Tez orada siz bilan bog'lanamiz.")
        await state.clear()

    return router


async def _run_subbot(owner_id: int, token: str) -> None:
    bot = Bot(token=token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(_build_customer_router(owner_id))
    try:
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot)
    except asyncio.CancelledError:
        raise
    except Exception:
        logger.exception(f"Sub-bot (owner={owner_id}) ishlashda xatolik yuz berdi")
    finally:
        await bot.session.close()


async def ensure_subbot_running(owner_id: int) -> None:
    """Agar owner_id uchun sub-bot allaqachon ishlamayotgan bo'lsa, uni ishga tushiradi."""
    existing = _running_subbots.get(owner_id)
    if existing and not existing.done():
        return

    subbots = await Store.get_all_subbots()
    entry = subbots.get(str(owner_id))
    if not entry or not entry.get("token"):
        return

    task = asyncio.create_task(_run_subbot(owner_id, entry["token"]))
    _running_subbots[owner_id] = task


async def start_all_registered_subbots() -> None:
    """Asosiy bot ishga tushganda, oldin ro'yxatdan o'tgan barcha sub-botlarni qayta yoqadi."""
    subbots = await Store.get_all_subbots()
    for owner_id_str, entry in subbots.items():
        if entry.get("active", True):
            await ensure_subbot_running(int(owner_id_str))
