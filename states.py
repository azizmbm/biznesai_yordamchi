"""
Barcha suhbat oqimlari (FSM) uchun holatlar (states).
"""
from aiogram.fsm.state import State, StatesGroup


class BusinessPlanFlow(StatesGroup):
    """1-tugma: 'Yangi biznes boshlash' oqimi."""
    waiting_business_name = State()
    waiting_location = State()
    waiting_own_capital = State()
    calculating = State()          # AI orqali xarajat/daromad hisoblanayotgan holat
    waiting_loan_term_choice = State()


class AiAssistantOnboarding(StatesGroup):
    """2-tugma: 'Biznes uchun AI yordamchi' — birinchi marta ro'yxatdan o'tish."""
    waiting_business_name_type = State()
    waiting_since_and_branches = State()
    waiting_advantages = State()
    waiting_disadvantages = State()
    waiting_social_profile = State()


class ContentGeneration(StatesGroup):
    """Instagram bio / Telegram bio / 30 kunlik SMM plan so'rovlari."""
    generating = State()


class SubBotSetup(StatesGroup):
    """AI sotuvchi — token olish va mahsulotlarni kiritish oqimi."""
    waiting_token = State()
    waiting_product_name_price = State()
    waiting_has_photo_choice = State()
    waiting_product_photo = State()
    waiting_min_quantity = State()


class CustomerOrderFlow(StatesGroup):
    """Sub-botdagi mijoz bilan suhbat (buyurtma qabul qilish)."""
    browsing = State()
    waiting_quantity = State()
    waiting_customer_name_phone = State()
    waiting_customer_address = State()
