"""
Bot bo'ylab ishlatiladigan barcha klaviaturalar (inline tugmalar).
"""
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def main_menu_kb() -> InlineKeyboardMarkup:
    """/start bosilganda chiqadigan 2 ta asosiy tugma."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🚀 Yangi biznes boshlash", callback_data="menu:new_business")],
        [InlineKeyboardButton(text="🤖 Biznes uchun AI yordamchi", callback_data="menu:ai_assistant")],
    ])


def yes_no_kb(prefix: str) -> InlineKeyboardMarkup:
    """Umumiy 'Ha / Yo'q' tugmalari (prefix orqali callback nomlanadi)."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Ha", callback_data=f"{prefix}:yes"),
            InlineKeyboardButton(text="❌ Yo'q", callback_data=f"{prefix}:no"),
        ]
    ])


def ai_assistant_hub_kb() -> InlineKeyboardMarkup:
    """To'liq ro'yxatdan o'tgan biznes egasi uchun asosiy AI-yordamchi menyusi."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📝 Instagram uchun bio", callback_data="ai:ig_bio")],
        [InlineKeyboardButton(text="📝 Telegram uchun bio", callback_data="ai:tg_bio")],
        [InlineKeyboardButton(text="📅 SMM plan (30 kunlik)", callback_data="ai:smm_plan")],
        [InlineKeyboardButton(text="🛒 AI sotuvchi", callback_data="ai:ai_seller")],
    ])


def product_has_photo_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📷 Bor", callback_data="product_photo:yes"),
            InlineKeyboardButton(text="🚫 Yo'q", callback_data="product_photo:no"),
        ]
    ])


def add_more_products_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Yangi mahsulot qo'shish", callback_data="product:add_more")],
        [InlineKeyboardButton(text="🏠 Bosh menyuga qaytish", callback_data="product:back_to_menu")],
    ])


def loan_term_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="12 oy", callback_data="loan_term:12")],
        [InlineKeyboardButton(text="24 oy", callback_data="loan_term:24")],
        [InlineKeyboardButton(text="36 oy", callback_data="loan_term:36")],
        [InlineKeyboardButton(text="48 oy", callback_data="loan_term:48")],
        [InlineKeyboardButton(text="📊 Barchasini solishtirish", callback_data="loan_term:all")],
    ])


def buy_confirm_kb(product_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🛒 Sotib olaman", callback_data=f"buy:{product_id}:yes")],
        [InlineKeyboardButton(text="⬅️ Ortga", callback_data="buy:back")],
    ])


def cart_action_kb() -> InlineKeyboardMarkup:
    """Mahsulot savatga qo'shilgandan keyin: yana mahsulot qo'shish yoki
    buyurtmani yakunlash (checkout)."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🛍 Yana mahsulot qo'shish", callback_data="cart:add_more")],
        [InlineKeyboardButton(text="✅ Buyurtmani rasmiylashtirish", callback_data="cart:checkout")],
    ])
