# Biznes-reja va AI-yordamchi Telegram bot

## O'rnatish

```bash
pip install -r requirements.txt
```

Muhit o'zgaruvchilarini o'rnating:

```bash
export BOT_TOKEN="asosiy_bot_tokeningiz"
export ANTHROPIC_API_KEY="claude_api_kalitingiz"
```

Ishga tushirish:

```bash
python bot.py
```

## Fayllar tuzilishi

- `bot.py` — asosiy kirish nuqtasi, barcha routerlarni ulaydi
- `config.py` — token, foiz stavkasi, imtiyozli davr kabi sozlamalar
- `states.py` — barcha suhbat oqimlari uchun FSM holatlari
- `keyboards.py` — inline tugmalar
- `storage.py` — JSON-fayl asosidagi saqlash (foydalanuvchi, mahsulot, sub-bot)
- `credit_calculator.py` — annuitet + imtiyozli davr bilan kredit hisob-kitobi
- `ai_content.py` — Claude API orqali xarajat baholash, bio va SMM-plan yaratish
- `pdf_generator.py` — bankka topshirish uchun professional PDF biznes-reja
- `subbot_manager.py` — har bir biznes egasi uchun "AI sotuvchi" sub-botini
  dinamik ishga tushiruvchi modul
- `smm_scheduler.py` — har 24 soatda SMM-plandan navbatdagi kunni yuboradi
- `handlers/` — barcha bosqichma-bosqich suhbat oqimlari

## Muhim eslatmalar

1. **Kredit stavkasi va imtiyozli davr** (`config.py` dagi
   `DEFAULT_ANNUAL_INTEREST_RATE`, `DEFAULT_GRACE_PERIOD_MONTHS`) — taxminiy
   qiymatlar. Haqiqiy bank shartlariga moslab sozlang yoki foydalanuvchidan
   so'rab, dinamik qilib bering.
2. **Xarajat/daromad prognozi** Claude API orqali baholanadi — bu haqiqiy
   bozor tadqiqoti (research) o'rnini bosuvchi taxminiy hisob-kitob. Aniqroq
   natija uchun bu funksiyani real narx bazasi/statistika API bilan
   almashtirish tavsiya etiladi.
3. **Saqlash**: hozirda oddiy JSON fayllar ishlatiladi. Foydalanuvchilar
   ko'payganda SQLite/PostgreSQL'ga o'tkazish tavsiya etiladi.
4. **Sub-botlar** long-polling rejimida, bitta process ichida asyncio
   tasklar sifatida ishlaydi. Bir nechta yuzlab sub-bot bo'lsa, webhook
   asosidagi arxitekturaga o'tish samaraliroq bo'ladi.
5. Mijoz bilan erkin muloqot (narx so'rash, savol-javob) hozircha oddiy
   qoidalar asosida ishlaydi (`subbot_manager.py` ichidagi
   `customer_free_text`) — buni to'liq AI-suhbat generatoriga
   (`ai_content.py` uslubida) almashtirish mumkin.
