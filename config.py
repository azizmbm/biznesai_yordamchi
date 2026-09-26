"""
Bot konfiguratsiyasi.
Barcha maxfiy qiymatlarni (token, API key) muhit o'zgaruvchilari (environment variables)
orqali bering — kodga hech qachon to'g'ridan-to'g'ri yozmang.
"""
import os
from dotenv import load_dotenv

# Loyiha papkasidagi .env faylini o'qib, muhit o'zgaruvchilariga yuklaydi.
# encoding="utf-8-sig": Windows/PowerShell orqali yaratilgan .env fayllar
# ko'pincha BOM belgisi bilan saqlanadi — bu BOM borligidan qat'iy nazar
# to'g'ri o'qilishini ta'minlaydi.
load_dotenv(encoding="utf-8-sig")

# Asosiy botning tokeni (@BotFather dan olinadi)
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")

# AI matn generatsiyasi (bio, SMM plan, biznes-xarajatlarni baholash) uchun
# Anthropic Claude API kaliti.
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
CLAUDE_MODEL = "claude-sonnet-4-6"

# --- Kredit hisob-kitobi uchun standart parametrlar ---
# Bu qiymatlar taxminiy va O'zbekiston bank tizimidagi haqiqiy shartlarga
# qarab o'zgarishi mumkin — foydalanuvchi bilan aniqlashtirib turing yoki
# botga sozlash imkoniyatini qo'shing.
DEFAULT_ANNUAL_INTEREST_RATE = 24.0   # yillik foiz stavkasi (%), taxminiy
DEFAULT_GRACE_PERIOD_MONTHS = 6       # imtiyozli (faqat foiz to'lanadigan) davr, oy
LOAN_TERMS_MONTHS = [12, 24, 36, 48]  # taqqoslash uchun muddatlar

# --- Fayl yo'llari ---
DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
USERS_DB_PATH = os.path.join(DATA_DIR, "users.json")
PRODUCTS_DB_PATH = os.path.join(DATA_DIR, "products.json")
SUBBOTS_DB_PATH = os.path.join(DATA_DIR, "subbots.json")
PDF_OUTPUT_DIR = os.path.join(DATA_DIR, "business_plans")
PRODUCT_PHOTOS_DIR = os.path.join(DATA_DIR, "product_photos")
