"""
Claude API orqali:
  1) Biznes ochish xarajatlari/daromadlarini taxminiy hisoblash (research o'rniga)
  2) Instagram/Telegram bio matnlarini yozish
  3) 30 kunlik SMM kontent-plan yaratish

Barcha funksiyalar async va httpx orqali to'g'ridan-to'g'ri Anthropic API'ga
murojaat qiladi (SDK shart emas, lekin xohlasangiz `anthropic` python
paketidan foydalanishingiz ham mumkin).
"""
import asyncio
import json
import re
from typing import Any, Dict, List, Optional

import httpx

from config import ANTHROPIC_API_KEY, CLAUDE_MODEL

ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"


async def _call_claude(system: str, user_prompt: str, max_tokens: int = 2000, timeout: float = 60) -> str:
    if not ANTHROPIC_API_KEY:
        raise RuntimeError(
            "ANTHROPIC_API_KEY o'rnatilmagan. Muhit o'zgaruvchisi sifatida qo'shing."
        )
    headers = {
        "x-api-key": ANTHROPIC_API_KEY,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }
    payload = {
        "model": CLAUDE_MODEL,
        "max_tokens": max_tokens,
        "system": system,
        "messages": [{"role": "user", "content": user_prompt}],
    }
    # DIQQAT: katta hajmdagi javoblar (masalan 30 kunlik SMM-plan) generatsiya
    # qilinishi bir necha o'n soniya vaqt olishi mumkin — timeout parametri
    # chaqiruvchi tomonidan kattaroq qilib berilishi mumkin, aks holda
    # httpx.ReadTimeout ko'tarilib, foydalanuvchiga tushunarsiz xatolik chiqadi.
    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.post(ANTHROPIC_URL, headers=headers, json=payload)
        resp.raise_for_status()
        data = resp.json()
    text_parts = [block["text"] for block in data.get("content", []) if block.get("type") == "text"]
    return "\n".join(text_parts).strip()


def _extract_json(raw_text: str) -> Dict[str, Any]:
    """
    Modeldan qaytgan javobdan JSON qismini ajratib oladi (agar u qo'shimcha
    matn yoki markdown ```-belgilar bilan kelsa).
    Javob kesilib qolgan (max_tokens'ga yetib to'xtagan) yoki umuman JSON
    bo'lmagan hollarda tushunarli ValueError ko'taradi — shunda chaqiruvchi
    kod foydalanuvchiga aniq xato xabarini ko'rsata oladi.
    """
    cleaned = re.sub(r"^```(json)?|```$", "", raw_text.strip(), flags=re.MULTILINE).strip()
    match = re.search(r"\{.*\}", cleaned, flags=re.DOTALL)
    json_str = match.group(0) if match else cleaned
    try:
        return json.loads(json_str)
    except json.JSONDecodeError as e:
        raise ValueError(
            "AI javobini o'qib bo'lmadi (JSON formatida emas yoki javob kesilib qolgan)."
        ) from e


def _extract_json_array(raw_text: str) -> list:
    """`_extract_json`ning JSON-massiv (list) uchun varianti.

    DIQQAT: agar javob `max_tokens` chegarasiga yetib o'rtada kesilib qolgan
    bo'lsa (masalan uzun SMM-plan bo'lagi), massivning yopuvchi `]` belgisi
    yo'q bo'lishi mumkin — bunday holda oddiy `json.loads` butunlay
    muvaffaqiyatsiz bo'lardi va TO'LIQ chiqqan kunlar ham yo'qolib ketardi.
    Shu sababli bu yerda avval to'liq massivni o'qishga harakat qilinadi,
    muvaffaqiyatsiz bo'lsa — matn ichidan TO'LIQ yopilgan `{...}` obyektlarini
    (kesilib qolgan oxirgisidan tashqari) birma-bir ajratib, ro'yxat sifatida
    qaytaradi. Chaqiruvchi kod (`generate_smm_plan`) yetishmagan kunlarni
    keyin alohida qayta so'raydi.
    """
    cleaned = re.sub(r"^```(json)?|```$", "", raw_text.strip(), flags=re.MULTILINE).strip()
    start = cleaned.find("[")
    if start == -1:
        raise ValueError(
            "AI javobini o'qib bo'lmadi (JSON formatida emas yoki javob kesilib qolgan). "
            "Iltimos, qaytadan urinib ko'ring."
        )

    try:
        return json.loads(cleaned[start:])
    except json.JSONDecodeError:
        pass

    # Javob kesilib qolgan bo'lishi mumkin — faqat TO'LIQ (ochilib-yopilgan)
    # obyektlarni tiklab olamiz, oxiridagi yarim qolgan obyektni tashlab yuboramiz.
    objects: list = []
    depth = 0
    obj_start: Optional[int] = None
    in_string = False
    escape = False
    for i in range(start + 1, len(cleaned)):
        ch = cleaned[i]
        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
        elif ch == "{":
            if depth == 0:
                obj_start = i
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0 and obj_start is not None:
                fragment = cleaned[obj_start:i + 1]
                try:
                    objects.append(json.loads(fragment))
                except json.JSONDecodeError:
                    pass
                obj_start = None

    if objects:
        return objects

    raise ValueError(
        "AI javobini o'qib bo'lmadi (JSON formatida emas yoki javob kesilib qolgan). "
        "Iltimos, qaytadan urinib ko'ring."
    )


async def estimate_business_costs(
    business_name: str,
    business_type: str,
    city: str,
    district: Optional[str],
    own_capital: float,
) -> Dict[str, Any]:
    """
    Berilgan biznes turi va manzil bo'yicha boshlang'ich xarajatlar va oylik
    moliyaviy prognozni taxminiy hisoblab, tuzilgan (structured) JSON qaytaradi.

    Qaytadigan kalitlar:
      rent_monthly, renovation_one_time, equipment_one_time, initial_goods_one_time,
      other_one_time_costs (list of {name, amount}), total_startup_cost,
      monthly_revenue_estimate, monthly_expenses_estimate, monthly_tax_estimate,
      monthly_net_profit_estimate, notes
    """
    location = f"{city}" + (f", {district}" if district else "")
    system = (
        "Siz O'zbekiston bozori bo'yicha tajribali biznes-tahlilchisiz. "
        "Faqat so'ralgan JSON formatida javob bering — hech qanday qo'shimcha matn, "
        "izoh yoki markdown belgilarisiz. Barcha summalarni so'mda, butun son sifatida bering."
    )
    user_prompt = f"""
Quyidagi biznes uchun O'zbekistondagi joriy bozor narxlariga asoslanib taxminiy
moliyaviy hisob-kitob tayyorlang:

- Biznes nomi: {business_name}
- Biznes turi/yo'nalishi: {business_type}
- Joylashuv: {location}
- Egasining o'z mablag'i: {own_capital:,.0f} so'm

Faqat quyidagi JSON strukturasida javob bering:
{{
  "rent_monthly": <number>,
  "renovation_one_time": <number>,
  "equipment_one_time": <number>,
  "initial_goods_one_time": <number>,
  "other_one_time_costs": [{{"name": "<nomi>", "amount": <number>}}],
  "total_startup_cost": <number>,
  "monthly_revenue_estimate": <number>,
  "monthly_expenses_estimate": <number>,
  "monthly_tax_estimate": <number>,
  "monthly_net_profit_estimate": <number>,
  "notes": "<qisqa 2-3 gapli izoh, bu raqamlar taxminiy ekanligi haqida>"
}}
"""
    raw = await _call_claude(system, user_prompt, max_tokens=1500)
    try:
        return _extract_json(raw)
    except ValueError:
        raw_retry = await _call_claude(
            system + " Javobingiz albatta to'liq va yopiq JSON obyekt bo'lishi shart.",
            user_prompt,
            max_tokens=1500,
        )
        return _extract_json(raw_retry)


async def negotiate_reply(
    product: Dict[str, Any],
    customer_message: str,
    chat_history: List[Dict[str, str]],
    preferences: List[str],
) -> Dict[str, Any]:
    """
    Sub-botdagi "AI sotuvchi" uchun asosiy funksiya: mijozning har qanday
    (savol, taklif, oddiy gap) xabariga — oldingi suhbat tarixi va shu
    mijoz haqida ma'lum bo'lgan afzalliklarni hisobga olib — javob yaratadi.

    Eski (keyword-based) yechimdan farqi:
      - Savdolashuv 1-2 xabardan keyin "tugab qolmaydi" — model butun
        suhbat tarixini ko'radi va context asosida davom ettiraveradi.
      - Yetkazib berish/to'lov/kafolat/qaytarish kabi savollarga qattiq
        qoidalar o'rniga tabiiy, kontekstga mos javob beradi.
      - Mijoz haqidagi foydali afzalliklarni ("preference_note") ajratib
        qaytaradi — chaqiruvchi kod buni Store.add_customer_preference bilan
        saqlaydi va keyingi barcha javoblarga ta'sir qiladi.

    DIQQAT (narx xavfsizligi): bu funksiya hech qachon `min_price`dan past
    "agreed_price" qaytarmasligi kerak — shunga qaramay, chaqiruvchi kod
    (`subbot_manager.py`) qaytgan narxni min_price bilan yana bir bor
    tekshiradi va faqat SHU MIJOZGA xos yozuvda saqlaydi (umumiy mahsulot
    narxini hech qachon o'zgartirmaydi).

    Qaytadigan kalitlar:
      reply (str) — mijozga yuboriladigan matn
      agreed_price (float | None) — agar aniq narxga kelishilgan bo'lsa
      preference_note (str | None) — mijoz haqida eslab qolinadigan qisqa izoh
    """
    current_price = product.get("current_price", 0)
    min_price = product.get("min_price", 0) or 0

    system = (
        "Siz onlayn do'kondagi professional AI-sotuvchisiz. Vazifangiz: "
        "mahsulotni sotish, mijoz bilan xushmuomalalik bilan (lekin "
        "tadbirkorona) savdolashish, mijozning savol va e'tirozlariga "
        "aniq va foydali javob berish, va mijoz haqida kelajakda foydali "
        "bo'ladigan afzalliklarni eslab qolish.\n\n"
        f"Hozir muhokama qilinayotgan mahsulot: {product.get('name')}\n"
        f"Joriy (ko'rsatilgan) narx: {current_price:,.0f} so'm\n"
        f"Minimal ruxsat etilgan narx (buni hech kimga aytmang va bundan "
        f"pastga HECH QACHON rozi bo'lmang): {min_price:,.0f} so'm\n\n"
        "Qoidalar:\n"
        "- Har doim oldin berilgan suhbat tarixini hisobga oling — mijoz "
        "nima haqida gapirayotganini (masalan, u nechanchi marta narx "
        "taklif qilyapti, avval nimalarni so'ragan) unutmang.\n"
        "- Savdolashuvni sun'iy ravishda 1-2 xabardan keyin to'xtatmang — "
        "mijoz bir necha marta qayta-qayta taklif qilsa ham, har safar "
        "kontekstga mos, tabiiy javob bering.\n"
        "- Mijoz min_price'dan yuqori yoki teng taklif qilsa — rozi bo'ling "
        "va shu narxni 'agreed_price' qilib qaytaring.\n"
        "- Mijoz min_price'dan past taklif qilsa — muloyimlik bilan rad "
        "eting va min_price'dan past bo'lmagan oraliq narx taklif qilishingiz "
        "mumkin (lekin 'agreed_price' faqat mijoz aniq rozi bo'lgandagina "
        "to'ldiriladi).\n"
        "- Yetkazib berish, to'lov, kafolat, qaytarish kabi savollarga "
        "tabiiy va aniq javob bering.\n"
        "- Mijoz o'zi haqida biror narsa aytsa (masalan yoqtirgan rangi, "
        "byudjeti, shoshilinchligi, oldin nimadir sotib olgani) — buni "
        "'preference_note' maydonida qisqa qilib yozing, aks holda null.\n\n"
        "Faqat quyidagi JSON formatida javob bering, hech qanday qo'shimcha "
        "matn yoki markdown qo'shmang:\n"
        '{"reply": "<mijozga yuboriladigan javob matni>", '
        '"agreed_price": <son yoki null>, '
        '"preference_note": "<qisqa izoh yoki null>"}'
    )

    history_lines = [
        f"{'Mijoz' if h.get('role') == 'customer' else 'Siz'}: {h.get('text', '')}"
        for h in chat_history[-20:]
    ]
    history_text = "\n".join(history_lines) if history_lines else "(hali suhbat bo'lmagan)"
    preferences_text = "; ".join(preferences) if preferences else "(hali ma'lum emas)"

    user_prompt = (
        f"Mijoz haqida ma'lum afzalliklar: {preferences_text}\n\n"
        f"Oldingi suhbat tarixi:\n{history_text}\n\n"
        f"Mijozning yangi xabari: {customer_message}"
    )

    try:
        raw = await _call_claude(system, user_prompt, max_tokens=500, timeout=30)
        result = _extract_json(raw)
    except Exception:
        return {
            "reply": "Kechirasiz, hozir aniq javob bera olmadim 🙂 Savolingizni "
                     "boshqacharoq qayta yozib ko'rasizmi?",
            "agreed_price": None,
            "preference_note": None,
        }

    agreed_price = result.get("agreed_price")
    if agreed_price is not None:
        try:
            agreed_price = float(agreed_price)
        except (TypeError, ValueError):
            agreed_price = None
        else:
            # Xavfsizlik uchun ikkinchi marta tekshiramiz: min_price'dan past
            # yoki joriy narxdan yuqori "kelishuv" hech qachon qabul qilinmaydi.
            if agreed_price < min_price or agreed_price > current_price:
                agreed_price = None

    return {
        "reply": result.get("reply") or "Kechirasiz, tushunmadim 🙂",
        "agreed_price": agreed_price,
        "preference_note": result.get("preference_note") or None,
    }


async def generate_bio(platform: str, profile: Dict[str, Any]) -> str:
    """Instagram yoki Telegram uchun bio matni yaratadi (platform: 'instagram' | 'telegram')."""
    max_len = 150 if platform == "instagram" else 500
    system = (
        f"Siz professional SMM-mutaxassissiz. O'zbek tilida, jonli va sotuvga "
        f"undovchi {platform} bio matni yozasiz. Javobda faqat tayyor bio matnini "
        f"bering, boshqa hech narsa qo'shmang."
    )
    user_prompt = f"""
Quyidagi biznes uchun {platform} bio yozing (~{max_len} belgigacha):
- Nomi va turi: {profile.get('name_type')}
- Faoliyat yuritish muddati va filiallar: {profile.get('since_and_branches')}
- Ustunliklari: {profile.get('advantages')}
- Kamchiliklari (ulardan foydalanmang, faqat kontekst uchun): {profile.get('disadvantages')}
"""
    return await _call_claude(system, user_prompt, max_tokens=300)


_SMM_PLAN_BATCH_SIZE = 5    # 30 kunni bittada emas, 6 ta (5 kunlik) bo'lakda so'raymiz
_SMM_PLAN_TOTAL_DAYS = 30
_SMM_PLAN_SYSTEM = (
    "Siz professional SMM-strategsiz va copywriter'siz. Faqat so'ralgan JSON "
    "massividan iborat javob bering, boshqa hech qanday matn qo'shmang. "
    "Har bir 'script' maydoni — mijozga to'g'ridan-to'g'ri joylash mumkin "
    "bo'lgan tayyor post matni bo'lishi kerak (hook, asosiy matn, CTA va "
    "2-3 ta mos hashtag bilan), 40-70 so'z atrofida."
)


async def _generate_smm_plan_batch(profile: Dict[str, Any], day_start: int, day_end: int) -> List[Dict[str, str]]:
    """`day_start`..`day_end` (ikkalasi ham qamrab olingan) kunlar uchun bitta bo'lak yaratadi."""
    user_prompt = f"""
Quyidagi biznes uchun {day_start}-kundan {day_end}-kungacha (jami {day_end - day_start + 1} kun)
kontent-plan tuzing:
- Nomi va turi: {profile.get('name_type')}
- Faoliyat yuritish muddati va filiallar: {profile.get('since_and_branches')}
- Ustunliklari: {profile.get('advantages')}
- Ijtimoiy tarmoq holati: {profile.get('social_profile')}

Har bir kun uchun mavzuni takrorlamang, turli xil kontent formatlarini
aralashtiring (tanishtiruv, mahsulot/xizmat namoyishi, mijoz fikri,
chegirma/aksiya, ortidagi jarayon, savol-javob, foydali maslahat va h.k.)

Faqat quyidagi JSON massiv formatida javob bering ({day_end - day_start + 1} ta element,
"day" maydoni {day_start} dan {day_end} gacha ketma-ket bo'lsin):
[
  {{
    "day": {day_start},
    "instagram_idea": "<kunning qisqa mavzusi/nomi, 5-8 so'z>",
    "instagram_script": "<Instagram uchun tayyor post matni>",
    "telegram_idea": "<kunning qisqa mavzusi/nomi, 5-8 so'z>",
    "telegram_script": "<Telegram uchun tayyor post matni>"
  }},
  ...
]
"""
    # DIQQAT: oldin bu yerda max_tokens=4096 edi. O'zbek tili tokenizatsiyada
    # (bir so'z ko'pincha 2-3 tokenga bo'linishi mumkin) 10 kunlik bo'lakning
    # to'liq JSON javobi ba'zan shu chegaraga yetib, javob O'RTADA kesilib
    # qolar edi — natijada butun bo'lak (hattoki muvaffaqiyatli yaratilgan
    # kunlar ham) "AI javobini o'qib bo'lmadi" xatoligi bilan yo'qolardi.
    # Claude Sonnet 4.6 minglab tokengacha chiqim qaytara oladi, shuning
    # uchun bu yerda ancha katta zахira (8192) qo'yilgan — bo'lak hajmi ham
    # (yuqorida) 10 dan 5 ga tushirilgan, shu ikkisi birgalikda kesilib
    # qolish ehtimolini deyarli yo'qqa chiqaradi.
    raw = await _call_claude(_SMM_PLAN_SYSTEM, user_prompt, max_tokens=8192, timeout=120)
    try:
        batch = _extract_json_array(raw)
    except ValueError:
        raw_retry = await _call_claude(
            _SMM_PLAN_SYSTEM + " Javobingiz albatta to'liq va yopiq JSON massiv bo'lishi shart.",
            user_prompt,
            max_tokens=8192,
            timeout=120,
        )
        batch = _extract_json_array(raw_retry)

    if not isinstance(batch, list) or not batch:
        raise ValueError(
            f"AI {day_start}-{day_end} kunlar uchun kontent-plan qaytarmadi. Qaytadan urinib ko'ring."
        )
    return batch


async def generate_smm_plan(profile: Dict[str, Any]) -> List[Dict[str, str]]:
    """
    30 kunlik SMM kontent-plan yaratadi. Har bir kun uchun nafaqat qisqa g'oya,
    balki to'liq tayyor post matni (ssenariy/caption, CTA va hashtaglar bilan)
    ham qaytariladi — shunchaki mavzu nomi emas.

    DIQQAT: 30 kunni bittada emas, 5 kunlik bo'laklarga (_SMM_PLAN_BATCH_SIZE)
    bo'lib so'raymiz. Sabab — 30 kunlik (va hatto 10 kunlik) to'liq JSON javob
    ba'zan model javobi max_tokens'ga urilib kesilib qolar va butun plan
    yaratilmasdan xatolik ("Xatolik: AI javobini o'qib bo'lmadi...") bilan
    tugardi. Kichik bo'laklar bilan bu ehtimol keskin kamayadi.

    MUHIM: bo'laklar bir-biridan mustaqil bo'lgani uchun ularni ASYNCIO.GATHER
    orqali PARALLEL (bir vaqtda) so'raymiz, ketma-ket emas. Oldin har bir
    bo'lak navbat bilan kutilardi — 6 ta bo'lak, har biri ~50-90 soniya
    bo'lsa, foydalanuvchi 5-9 daqiqa kutishga majbur bo'lardi. Parallel
    yuborilganda umumiy kutish vaqti bitta bo'lakning vaqtiga teng bo'ladi
    (~60-90 soniya), bo'laklar sonidan qat'iy nazar.

    Yana bir himoya qatlami: agar biror bo'lak baribir to'liq bo'lib chiqmasa
    (`_extract_json_array` faqat qisman tiklab olgan bo'lsa), shu bo'lakdagi
    YETISHMAGAN kunlar aniqlanadi va ular oxirida yana bitta parallel
    so'rov to'plamida qayta so'raladi — foydalanuvchiga xatolik umuman
    ko'rsatilmaydi.
    """
    batch_ranges = []
    for day_start in range(1, _SMM_PLAN_TOTAL_DAYS + 1, _SMM_PLAN_BATCH_SIZE):
        day_end = min(day_start + _SMM_PLAN_BATCH_SIZE - 1, _SMM_PLAN_TOTAL_DAYS)
        batch_ranges.append((day_start, day_end))

    batches = await asyncio.gather(
        *[_generate_smm_plan_batch(profile, s, e) for s, e in batch_ranges]
    )

    plan: List[Dict[str, str]] = []
    missing_days: List[int] = []
    for (day_start, day_end), batch in zip(batch_ranges, batches):
        plan.extend(batch)
        got_days = {item.get("day") for item in batch if isinstance(item, dict)}
        missing_days.extend(d for d in range(day_start, day_end + 1) if d not in got_days)

    if missing_days:
        # Bitta kunlik "bo'lak"lar sifatida, yana parallel qayta so'raymiz —
        # juda kichik so'rovlar bo'lgani uchun kesilib qolish ehtimoli deyarli nol.
        fix_batches = await asyncio.gather(
            *[_generate_smm_plan_batch(profile, d, d) for d in missing_days]
        )
        for fix_batch in fix_batches:
            plan.extend(fix_batch)

    plan.sort(key=lambda item: item.get("day", 0))

    if not plan:
        raise ValueError("AI 30 kunlik kontent-plan qaytarmadi. Qaytadan urinib ko'ring.")
    return plan
