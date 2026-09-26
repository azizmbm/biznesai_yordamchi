from aiogram import Router, F
from aiogram.filters import CommandStart
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from keyboards import main_menu_kb, ai_assistant_hub_kb
from states import BusinessPlanFlow, AiAssistantOnboarding
from storage import Store

router = Router(name="start")


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(
        "Assalomu alaykum! 👋\n\n"
        "Men sizga yangi biznes ochishda hisob-kitob qilishda yoki "
        "mavjud biznesingiz uchun AI yordamchi sifatida xizmat qilaman.\n\n"
        "Quyidagilardan birini tanlang:",
        reply_markup=main_menu_kb(),
    )


@router.callback_query(F.data == "menu:new_business")
async def on_new_business(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(BusinessPlanFlow.waiting_business_name)
    await callback.message.edit_text(
        "🚀 Yangi biznes uchun hisob-kitob boshlaymiz.\n\n"
        "1️⃣ Biznesingiz nomi va yo'nalishini kiriting.\n"
        "Masalan: <i>Salvador kiyim do'koni</i>"
    )
    await callback.answer()


@router.callback_query(F.data == "menu:ai_assistant")
async def on_ai_assistant(callback: CallbackQuery, state: FSMContext) -> None:
    profile = await Store.get_user(callback.from_user.id)
    if profile.get("onboarded"):
        await callback.message.edit_text(
            f"Xush kelibsiz, <b>{profile.get('name_type', '')}</b>! 🤖\n\n"
            "Quyidagi xizmatlardan birini tanlang:",
            reply_markup=ai_assistant_hub_kb(),
        )
    else:
        await state.set_state(AiAssistantOnboarding.waiting_business_name_type)
        await callback.message.edit_text(
            "🤖 Keling, avval biznesingiz haqida qisqacha tanishaylik.\n\n"
            "1️⃣ Biznesingiz nomini va turini kiriting.\n"
            "Masalan: <i>Salvador kiyim do'koni, Safia cafe, Asnam Tekstil</i>"
        )
    await callback.answer()
