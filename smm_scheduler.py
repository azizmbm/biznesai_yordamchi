"""
Har 24 soatda foydalanuvchining saqlangan 30-kunlik SMM-planidan navbatdagi
kun g'oyasini yuboruvchi fon vazifasi (background task).
"""
import asyncio
import logging
import time

from aiogram import Bot

from storage import Store

logger = logging.getLogger(__name__)

CHECK_INTERVAL_SECONDS = 60 * 60          # har soatda tekshiradi
SEND_INTERVAL_SECONDS = 24 * 60 * 60      # 24 soatda bir marta yuboradi


async def run_smm_scheduler(bot: Bot) -> None:
    while True:
        try:
            users = await Store.get_all_users()
            now = time.time()
            for user_id_str, profile in users.items():
                plan = profile.get("smm_plan")
                if not plan:
                    continue
                day_index = profile.get("smm_plan_day_index", 0)
                last_sent_at = profile.get("smm_plan_last_sent_at", 0)

                if day_index >= len(plan):
                    continue
                if now - last_sent_at < SEND_INTERVAL_SECONDS:
                    continue

                day_content = plan[day_index]
                try:
                    await bot.send_message(
                        int(user_id_str),
                        f"📅 <b>{day_content['day']}-kun uchun tayyor kontent:</b>\n\n"
                        f"📸 <b>Instagram</b> ({day_content['instagram_idea']}):\n"
                        f"{day_content['instagram_script']}\n\n"
                        f"✈️ <b>Telegram</b> ({day_content['telegram_idea']}):\n"
                        f"{day_content['telegram_script']}",
                    )
                except Exception:
                    logger.exception(f"SMM-plan xabarini {user_id_str} ga yuborib bo'lmadi")

                await Store.update_user(
                    int(user_id_str),
                    smm_plan_day_index=day_index + 1,
                    smm_plan_last_sent_at=now,
                )
        except Exception:
            logger.exception("SMM scheduler tsiklida xatolik")

        await asyncio.sleep(CHECK_INTERVAL_SECONDS)
