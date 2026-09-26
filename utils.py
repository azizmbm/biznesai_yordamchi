"""
Butun loyiha bo'ylab ishlatiladigan umumiy matn/son parsing funksiyalari.

Bu modul quyidagi muammolarning oldini olish uchun yaratilgan:
  - Foydalanuvchi matn kutilayotgan joyda rasm/stiker/lokatsiya/ovozli xabar
    yuborsa, `message.text` None bo'ladi va `.strip()` chaqirilganda bot
    AttributeError bilan yiqiladi. `safe_text()` buni xavfsiz tarzda hal qiladi.
  - Foydalanuvchilar summani turlicha yozadi: "3800000", "3 800 000",
    "3.800.000", "3,6 mln", "500 ming" va h.k. `parse_amount_uz()` bularning
    barchasini bir xil songa aylantiradi.
  - Miqdorni ("nechta") ba'zan so'z bilan yozishadi ("ikkita", "uchta").
    `parse_quantity()` buni ham tushunadi.
"""
import re
from typing import Optional

_NUMBER_WORDS = {
    "bitta": 1, "bir": 1,
    "ikkita": 2, "ikki": 2,
    "uchta": 3, "uch": 3,
    "to'rtta": 4, "tortta": 4, "to'rt": 4, "tort": 4,
    "beshta": 5, "besh": 5,
    "oltita": 6, "olti": 6,
    "yettita": 7, "yetti": 7,
    "sakkizta": 8, "sakkiz": 8,
    "to'qqizta": 9, "toqqizta": 9, "to'qqiz": 9, "toqqiz": 9,
    "o'nta": 10, "onta": 10, "o'n": 10, "on": 10,
}


def safe_text(raw_text: Optional[str]) -> Optional[str]:
    """
    `message.text`ni xavfsiz tarzda tozalab qaytaradi.
    Agar matn bo'lmasa (rasm, stiker, lokatsiya va h.k. yuborilgan bo'lsa)
    yoki bo'sh bo'lsa — None qaytaradi (hech qachon AttributeError bermaydi).
    """
    if raw_text is None:
        return None
    stripped = raw_text.strip()
    return stripped if stripped else None


def parse_amount_uz(text: Optional[str]) -> Optional[float]:
    """
    Foydalanuvchi kiritgan pul summasini so'mda (butun son, float) qaytaradi.

    Qo'llab-quvvatlanadigan formatlar:
      "3800000"          -> 3_800_000
      "3 800 000"        -> 3_800_000
      "3.800.000"        -> 3_800_000
      "3,6 mln"          -> 3_600_000
      "3.6 million"      -> 3_600_000
      "500 ming"         -> 500_000
      "30000000 so'm"    -> 30_000_000

    Raqam topilmasa None qaytaradi.
    """
    text = safe_text(text)
    if text is None:
        return None
    t = text.lower().replace("so'm", "").replace("sum", "").replace("сум", "")

    # "3,6 mln" / "3.6 million" / "3,6 млн"
    m = re.search(r"(\d+(?:[.,]\d+)?)\s*(mln|million|млн)", t)
    if m:
        return float(m.group(1).replace(",", ".")) * 1_000_000

    # "500 ming" / "500ming"
    m = re.search(r"(\d+(?:[.,]\d+)?)\s*(ming|тыс)", t)
    if m:
        return float(m.group(1).replace(",", ".")) * 1_000

    digits_only = re.sub(r"[^\d]", "", t)
    if digits_only:
        return float(digits_only)

    return None


def parse_quantity(text: Optional[str], default: int = 1) -> int:
    """
    Miqdorni matndan ajratib oladi: "2", "2 dona", "ikkita" va h.k.
    Aniqlab bo'lmasa `default` qaytaradi (0 yoki manfiy son hech qachon
    qaytarilmaydi).
    """
    text = safe_text(text)
    if text is None:
        return default
    t = text.lower()
    for word, value in _NUMBER_WORDS.items():
        if word in t:
            return value
    digits = "".join(ch for ch in t if ch.isdigit())
    if digits:
        value = int(digits)
        return value if value > 0 else default
    return default


def looks_like_phone(token: str) -> bool:
    """Berilgan so'z telefon raqamiga o'xshaydimi (kamida 7 ta raqam bor)."""
    return sum(ch.isdigit() for ch in token) >= 7
