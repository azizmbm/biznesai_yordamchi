"""
Oddiy JSON-fayl asosidagi saqlash qatlami.

Eslatma: bu yechim kichik/o'rta yuklama uchun yetarli. Foydalanuvchilar soni
ko'payib, bir vaqtda ko'p yozish kerak bo'lsa — SQLite yoki Postgres'ga
o'tish tavsiya etiladi (masalan SQLAlchemy bilan).
"""
import json
import os
import asyncio
from typing import Any, Dict, List, Optional

from config import DATA_DIR, USERS_DB_PATH, PRODUCTS_DB_PATH, SUBBOTS_DB_PATH, PDF_OUTPUT_DIR

_lock = asyncio.Lock()

MAX_CHAT_HISTORY = 30       # mijoz bilan saqlanadigan oxirgi necha xabar (AI kontekst uchun)
MAX_PREFERENCES = 20        # mijoz haqida saqlanadigan oxirgi necha "eslatma"


def _ensure_dirs() -> None:
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(PDF_OUTPUT_DIR, exist_ok=True)


def _read_json(path: str) -> Dict[str, Any]:
    _ensure_dirs()
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return {}


def _write_json(path: str, data: Dict[str, Any]) -> None:
    _ensure_dirs()
    tmp_path = path + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp_path, path)


class Store:
    """Foydalanuvchi profillari, mahsulotlar va sub-botlar uchun yagona interfeys."""

    # ---------- Foydalanuvchi (biznes egasi) profili ----------
    @staticmethod
    async def get_user(user_id: int) -> Dict[str, Any]:
        async with _lock:
            users = _read_json(USERS_DB_PATH)
            return users.get(str(user_id), {})

    @staticmethod
    async def update_user(user_id: int, **fields: Any) -> Dict[str, Any]:
        async with _lock:
            users = _read_json(USERS_DB_PATH)
            profile = users.get(str(user_id), {})
            profile.update(fields)
            users[str(user_id)] = profile
            _write_json(USERS_DB_PATH, users)
            return profile

    @staticmethod
    async def get_all_users() -> Dict[str, Any]:
        """Faqat haqiqiy biznes-egasi profillarini qaytaradi (mijoz yozuvlarisiz)."""
        async with _lock:
            users = _read_json(USERS_DB_PATH)
            return {k: v for k, v in users.items() if not k.startswith("customer:")}

    # ---------- Mahsulotlar (har bir biznes egasi uchun ro'yxat) ----------
    @staticmethod
    async def add_product(owner_id: int, product: Dict[str, Any]) -> str:
        async with _lock:
            products = _read_json(PRODUCTS_DB_PATH)
            owner_products = products.get(str(owner_id), {})
            product_id = str(len(owner_products) + 1)
            owner_products[product_id] = product
            products[str(owner_id)] = owner_products
            _write_json(PRODUCTS_DB_PATH, products)
            return product_id

    @staticmethod
    async def get_products(owner_id: int) -> Dict[str, Any]:
        async with _lock:
            products = _read_json(PRODUCTS_DB_PATH)
            return products.get(str(owner_id), {})

    @staticmethod
    async def update_product_price(owner_id: int, product_id: str, new_price: float) -> None:
        """
        DIQQAT: bu UMUMIY narxni o'zgartiradi — natija BARCHA mijozlarga
        ko'rinadi. Mijoz bilan savdolashib kelishilgan SHAXSIY narx uchun
        buni hech qachon chaqirmang — buning o'rniga
        `set_negotiated_price(owner_id, customer_tg_id, product_id, price)`
        dan foydalaning (faqat shu mijozga ko'rsatiladi).
        """
        async with _lock:
            products = _read_json(PRODUCTS_DB_PATH)
            owner_products = products.get(str(owner_id), {})
            if product_id in owner_products:
                owner_products[product_id]["current_price"] = new_price
                products[str(owner_id)] = owner_products
                _write_json(PRODUCTS_DB_PATH, products)

    # ---------- Sub-botlar (AI sotuvchi tokenlari) ----------
    @staticmethod
    async def register_subbot(owner_id: int, token: str) -> None:
        async with _lock:
            subbots = _read_json(SUBBOTS_DB_PATH)
            subbots[str(owner_id)] = {"token": token, "active": True}
            _write_json(SUBBOTS_DB_PATH, subbots)

    @staticmethod
    async def get_subbot_token(owner_id: int) -> Optional[str]:
        """Agar shu biznes egasi uchun sub-bot tokeni allaqachon ro'yxatdan
        o'tgan bo'lsa, uni qaytaradi (aks holda None)."""
        async with _lock:
            subbots = _read_json(SUBBOTS_DB_PATH)
            entry = subbots.get(str(owner_id))
            return entry.get("token") if entry else None

    @staticmethod
    async def get_all_subbots() -> Dict[str, Any]:
        async with _lock:
            return _read_json(SUBBOTS_DB_PATH)

    # ---------- Mijozlar (sub-bot ichida, qayta so'ramaslik uchun) ----------
    @staticmethod
    async def save_customer(owner_id: int, customer_tg_id: int, name: str, phone: str) -> None:
        async with _lock:
            users = _read_json(USERS_DB_PATH)
            key = f"customer:{owner_id}:{customer_tg_id}"
            # DIQQAT: mavjud yozuvni (chat_history, preferences, negotiated_prices)
            # o'chirib tashlamaslik uchun to'liq almashtirish o'rniga faqat
            # name/phone maydonlarini yangilaymiz.
            customer = users.get(key, {})
            customer["name"] = name
            customer["phone"] = phone
            users[key] = customer
            _write_json(USERS_DB_PATH, users)

    @staticmethod
    async def get_customer(owner_id: int, customer_tg_id: int) -> Dict[str, Any]:
        async with _lock:
            users = _read_json(USERS_DB_PATH)
            return users.get(f"customer:{owner_id}:{customer_tg_id}", {})

    # ---------- AI sotuvchi uchun: mijoz bilan suhbat tarixi ----------
    @staticmethod
    async def get_customer_chat_history(owner_id: int, customer_tg_id: int) -> List[Dict[str, str]]:
        async with _lock:
            users = _read_json(USERS_DB_PATH)
            customer = users.get(f"customer:{owner_id}:{customer_tg_id}", {})
            return customer.get("chat_history", [])

    @staticmethod
    async def append_customer_message(owner_id: int, customer_tg_id: int, role: str, text: str) -> None:
        """role: 'customer' yoki 'bot'."""
        async with _lock:
            users = _read_json(USERS_DB_PATH)
            key = f"customer:{owner_id}:{customer_tg_id}"
            customer = users.get(key, {})
            history = customer.get("chat_history", [])
            history.append({"role": role, "text": text})
            customer["chat_history"] = history[-MAX_CHAT_HISTORY:]
            users[key] = customer
            _write_json(USERS_DB_PATH, users)

    # ---------- AI sotuvchi uchun: mijoz haqida eslab qolinadigan afzalliklar ----------
    @staticmethod
    async def get_customer_preferences(owner_id: int, customer_tg_id: int) -> List[str]:
        async with _lock:
            users = _read_json(USERS_DB_PATH)
            customer = users.get(f"customer:{owner_id}:{customer_tg_id}", {})
            return customer.get("preferences", [])

    @staticmethod
    async def add_customer_preference(owner_id: int, customer_tg_id: int, note: str) -> None:
        async with _lock:
            users = _read_json(USERS_DB_PATH)
            key = f"customer:{owner_id}:{customer_tg_id}"
            customer = users.get(key, {})
            prefs = customer.get("preferences", [])
            if note not in prefs:
                prefs.append(note)
            customer["preferences"] = prefs[-MAX_PREFERENCES:]
            users[key] = customer
            _write_json(USERS_DB_PATH, users)

    # ---------- AI sotuvchi uchun: HAR BIR MIJOZGA XOS kelishilgan narx ----------
    # DIQQAT: bu narxlar `products.json`dagi umumiy (barcha mijozlar uchun bir xil)
    # `current_price`ga HECH QACHON yozilmaydi — faqat shu bitta mijoz uchun,
    # shu mijozning yozuvida saqlanadi. Shu tufayli bitta mijoz bilan
    # savdolashib kelishilgan narx boshqa mijozlarga umuman ta'sir qilmaydi.
    @staticmethod
    async def get_negotiated_price(owner_id: int, customer_tg_id: int, product_id: str) -> Optional[float]:
        async with _lock:
            users = _read_json(USERS_DB_PATH)
            customer = users.get(f"customer:{owner_id}:{customer_tg_id}", {})
            return customer.get("negotiated_prices", {}).get(product_id)

    @staticmethod
    async def set_negotiated_price(owner_id: int, customer_tg_id: int, product_id: str, price: float) -> None:
        async with _lock:
            users = _read_json(USERS_DB_PATH)
            key = f"customer:{owner_id}:{customer_tg_id}"
            customer = users.get(key, {})
            prices = customer.get("negotiated_prices", {})
            prices[product_id] = price
            customer["negotiated_prices"] = prices
            users[key] = customer
            _write_json(USERS_DB_PATH, users)
