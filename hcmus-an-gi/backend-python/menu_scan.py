"""Doc nhieu anh menu bang Gemini Vision -> JSON mon + gia + thong tin quan."""
from __future__ import annotations

import json
import os
import re
import time
from typing import Any

from google import genai
from google.genai import types

# Model mac dinh + danh sach du phong. Gemini hay ngung model cu, nen neu model dau
# bao 404/khong ton tai thi thu model ke tiep. Co the ep model bang GEMINI_MODEL trong .env.
FALLBACK_MODELS = ["gemini-3.8-flash", "gemini-3.6-flash", "gemini-2.5-flash"]

PROMPT = """Ban la OCR menu quan an Viet Nam cho sinh vien.
Cac anh gui kem la CAC TRANG CUA CUNG MOT MENU (co the chet, nghieng, chup bang dien thoai).
Doc tat ca anh, GOP lai thanh mot danh sach, khong lap mon.
Tra ve DUNG JSON (khong markdown) theo schema:
{
  "restaurant_hint": "ten quan neu thay tren menu, else null",
  "phone": "so dien thoai neu co, else null",
  "hours": "gio mo cua neu co tren menu, else null",
  "address_hint": "dia chi neu co tren menu, else null",
  "currency": "VND",
  "dishes": [
    {"name": "ten mon", "price": 35000, "category": "nhom mon (Com, Mi, Nuoc uong, Topping...) hoac null", "note": "size/ghi chu ngan hoac null"}
  ],
  "notes": ["ghi chu chung cua quan: freeship, phu thu, VAT, khuyen mai, topping +5k..."]
}
Quy tac:
- price la so nguyen VND. "35k"/"35.000d"/"35" (menu ghi gia theo nghin) -> 35000.
- Mon co nhieu size (S/M/L) thi tach thanh cac dong rieng hoac ghi size trong note, gia dung voi tung size.
- Mon khong doc duoc gia van them voi price=null.
- Giu nguyen tieng Viet co dau cua ten mon.
- Khong bia mon, gia, so dien thoai khong co tren anh.
"""


def _models_to_try() -> list[str]:
    forced = (os.getenv("GEMINI_MODEL") or "").strip()
    out = [forced] if forced else []
    out += [m for m in FALLBACK_MODELS if m not in out]
    return out


def _is_model_missing(err: Exception) -> bool:
    t = str(err).lower()
    return any(k in t for k in ("404", "not found", "no longer available", "is not supported", "deprecated"))


def _is_overloaded(err: Exception) -> bool:
    """503 UNAVAILABLE / 429 / high demand: tam thoi, nen thu lai hoac doi model."""
    t = str(err).lower()
    return any(k in t for k in ("503", "unavailable", "429", "resource_exhausted", "high demand", "overloaded", "timed out", "deadline"))


def _to_int_price(v: Any) -> int | None:
    if v is None:
        return None
    try:
        n = int(float(str(v).replace(",", "").replace(".", "")) if isinstance(v, str) else float(v))
    except (TypeError, ValueError):
        return None
    return n if n >= 0 else None


def scan_menu_images(images: list[tuple[bytes, str]]) -> dict[str, Any]:
    if not images:
        raise ValueError("Khong co anh nao")
    api_key = (os.getenv("GEMINI_API_KEY") or "").strip()
    if not api_key:
        raise ValueError("Chua cau hinh GEMINI_API_KEY trong backend-python/.env")

    client = genai.Client(api_key=api_key)
    contents: list[Any] = [types.Part.from_bytes(data=b, mime_type=m) for b, m in images]
    contents.append(PROMPT)
    config = types.GenerateContentConfig(temperature=0.1, response_mime_type="application/json")

    response = None
    last_err: Exception | None = None
    for model in _models_to_try():
        for attempt in range(3):  # model dang qua tai -> thu lai 3 lan (2s, 5s) roi doi model
            try:
                response = client.models.generate_content(model=model, contents=contents, config=config)
                break
            except Exception as e:  # noqa: BLE001
                last_err = e
                if _is_overloaded(e):
                    if attempt < 2:
                        time.sleep(2 if attempt == 0 else 5)
                    continue
                if _is_model_missing(e):
                    break  # model khong con -> doi model ke tiep
                raise
        if response is not None:
            break
    if response is None:
        if last_err is not None and _is_overloaded(last_err):
            raise RuntimeError(
                "Gemini dang qua tai (503). Da thu lai nhieu lan va doi model nhung chua duoc. "
                "Hay bam 'AI doc menu' lai sau 1-2 phut."
            )
        raise RuntimeError(
            f"Khong model Gemini nao dung duoc ({', '.join(_models_to_try())}). "
            f"Dat GEMINI_MODEL trong .env theo model dang con hieu luc. Loi cuoi: {last_err}"
        )

    text = (response.text or "").strip()
    if not text:
        raise ValueError("Gemini khong tra noi dung tu anh menu")
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    data = json.loads(text)

    seen: set[tuple[str, int | None]] = set()
    cleaned = []
    for d in data.get("dishes") or []:
        if not isinstance(d, dict):
            continue
        name = str(d.get("name") or "").strip()
        if not name:
            continue
        price = _to_int_price(d.get("price"))
        if price is not None and 0 < price < 1000:  # menu ghi gia theo nghin dong (vd 35 = 35.000d)
            price *= 1000
        key = (re.sub(r"\s+", " ", name.lower()), price)
        if key in seen:
            continue
        seen.add(key)
        cleaned.append(
            {
                "name": name[:180],
                "price": price,
                "category": (str(d.get("category") or "").strip()[:120] or None),
                "note": (str(d.get("note") or "").strip()[:255] or None),
            }
        )
        if len(cleaned) >= 150:
            break

    notes = [str(n).strip() for n in (data.get("notes") or []) if str(n).strip()]

    def opt(key: str, limit: int = 255):
        v = str(data.get(key) or "").strip()
        return v[:limit] or None

    return {
        "restaurant_hint": opt("restaurant_hint", 180),
        "phone": opt("phone", 60),
        "hours": opt("hours"),
        "address_hint": opt("address_hint", 500),
        "currency": data.get("currency") or "VND",
        "dishes": cleaned,
        "notes": notes,
        "raw_notes": "\n".join(notes) or None,
    }


def scan_menu_image(image_bytes: bytes, mime: str = "image/jpeg") -> dict[str, Any]:
    """Giu ham cu cho code goi mot anh."""
    return scan_menu_images([(image_bytes, mime)])