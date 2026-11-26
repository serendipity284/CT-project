"""Food and place name extraction and database search helpers."""

import re
import unicodedata
from typing import Optional, NamedTuple

from .context import UNLIMITED_PATTERNS


class FoodExtractionResult(NamedTuple):
    food_name: Optional[str]
    place_name: Optional[str]
    preference: Optional[str]


def remove_accents(text: str) -> str:
    """Loại bỏ dấu tiếng Việt."""
    if not text:
        return ""
    text = text.replace("đ", "d").replace("Đ", "D")
    text = unicodedata.normalize("NFD", text)
    return "".join(c for c in text if unicodedata.category(c) != "Mn")


def slugify_food(food_name: Optional[str]) -> Optional[str]:
    """
    Chuyển đổi động bất kỳ tên món ăn nào thành canonical slug chuẩn hóa dạng snake_case.

    Ví dụ:
        "Cơm tấm"              -> "com_tam"
        "Cơm tấm sườn bì chả"  -> "com_tam_suon_bi_cha"
        "Phở bò"               -> "pho_bo"
        "Bánh mì chảo"         -> "banh_mi_chao"
        "Mì cay 7 cấp độ"      -> "mi_cay_7_cap_do"
        "Takoyaki"             -> "takoyaki"
    """
    if not food_name:
        return None

    cleaned = food_name.strip()
    if not cleaned:
        return None

    # Bỏ dấu tiếng Việt và chuyển chữ thường
    no_accents = remove_accents(cleaned).lower()

    # Thay thế các ký tự không phải chữ/số thành gạch dưới
    slug = re.sub(r"[^a-z0-9]+", "_", no_accents)

    # Xóa gạch dưới thừa ở đầu/cuối/liên tiếp
    slug = re.sub(r"_+", "_", slug).strip("_")

    return slug or None


def extract_search_keywords(food_name: Optional[str], search_slug: Optional[str] = None) -> list[str]:
    """
    Trích xuất động các từ khóa tìm kiếm để khớp vào places.cuisine và places.name trong MySQL.

    Không dùng mapping tĩnh; phân tích trực tiếp từ food_name và search_slug:
    - Lấy cụm tên gốc (ví dụ: "cơm tấm")
    - Lấy các danh từ chính (ví dụ: "cơm", "tấm", "phở", "bún")
    """
    keywords: list[str] = []

    if food_name:
        fn = food_name.strip()
        keywords.append(fn)

        # Tách các từ riêng lẻ có nghĩa (bỏ các từ nối ngắn)
        words = fn.split()
        if len(words) > 1:
            for w in words:
                if len(w) >= 2 and w.lower() not in ("quán", "tiệm", "ăn", "ngon", "ở", "gần"):
                    keywords.append(w)

    if search_slug:
        parts = search_slug.split("_")
        for p in parts:
            if len(p) >= 2 and p not in ("quan", "tiem", "an", "ngon", "o", "gan"):
                keywords.append(p)

    # Loại bỏ trùng lặp giữ nguyên thứ tự
    seen = set()
    unique_keywords = []
    for k in keywords:
        k_lower = k.lower()
        if k_lower not in seen:
            seen.add(k_lower)
            unique_keywords.append(k)

    return unique_keywords


# ---------------------------------------------------------------------------
# Fallback trích xuất món ăn cơ bản khi Gemini gặp sự cố (Offline / Không có API Key)
# Dựa trên cấu trúc ngữ pháp tiếng Việt: "ăn <món>", "quán <món>", "thèm <món>"
# ---------------------------------------------------------------------------

# Match boundaries on the original text so names retain accents and punctuation.
_BOUNDARY = re.compile(
    r"[,;!?]|\s+(?:ở|tại|gần|gan|dưới|duoi|trong bán kính|ngân sách|ngan sach|"
    r"cho (?:tôi|mình)|giúp tôi|được không|được ko|quanh|ngon ở|giá|gia|không cay|khong cay|nhé|nha|giúp mình|quận\s+\d+|q\d+)\b"
    r"|\s+(?:(?:tầm|khoảng|tam|khoang)\s+)?\d+(?:[.,]\d+)?\s*(?:k|đ|nghìn|ngàn|km|m)\b", re.I
)
_VENUE = re.compile(r"\b(?:(ở|tại|o|tai)\s+)?(quán|quan|tiệm|tiem|nhà hàng|nha hang)\s+", re.I)
_FOOD = re.compile(
    r"\b(?:muốn ăn|muon an|ăn|an|thèm|them|đổi sang|doi sang|gợi ý món|goi y mon|"
    r"tìm|tim|bán|ban)\s+(?:(?:quán|quan|món|mon)\s+)?(?:(?:bán|ban)\s+)?", re.I
)


def _name(fragment: str) -> Optional[str]:
    value = _BOUNDARY.split(" " + fragment.strip(), maxsplit=1)[0].strip(" \t\n.,!?")
    return value or None


def fallback_extract_food(text: str) -> FoodExtractionResult:
    text = unicodedata.normalize("NFC", text.strip())
    # Remove filter clauses before extracting a dish or venue from the same turn.
    normalized = remove_accents(text).lower()
    spans = [match.span() for pattern in UNLIMITED_PATTERNS.values()
             for match in pattern.finditer(normalized)]
    if spans:
        chars = list(text)
        for start, end in spans:
            chars[start:end] = "," * (end - start)
        text = "".join(chars)
    lower = text.lower()

    # Nhận diện sở thích cơ bản nếu có trong câu
    preference = None
    if "không cay" in lower or "khong cay" in lower:
        preference = "khong_cay"
    elif "cay" in lower:
        preference = "cay"
    elif "chay" in lower:
        preference = "chay"
    elif "thanh đạm" in lower or "thanh dam" in lower:
        preference = "thanh_dam"

    place_name = None
    for marker in _VENUE.finditer(text):
        tail = text[marker.end():]
        sale = re.search(r"\s+(?:bán|ban|có bán)\s+", tail, re.I)
        candidate = _name(tail[:sale.start()] if sale else tail)
        if not candidate or candidate[0].isdigit() or re.match(r"(?:bán|ban)\b", candidate, re.I):
            continue
        if marker[1] or candidate[0].isupper() or sale:
            place_name = candidate
            text = text[:marker.start()] + (" bán " + tail[sale.end():] if sale else "")
            break

    cue = _FOOD.search(text)
    food_name = _name(text[cue.end():]) if cue else None
    if not cue:
        # Accept short standalone names, but exclude conversational and filter updates.
        generic = re.search(
            r"\b(?:hôm nay|mình|tôi|buồn|vui|stress|mệt|deadline|ngân sách|bán kính|"
            r"tăng|giảm|quận|làng|xin chào|cảm ơn|không|muốn|đang|tìm|tim|tại|tai|chỉ|khong|thu duc|linh trung|nguyễn văn cừ|q\d+)\b", text, re.I
        )
        if not generic and text[:1].isalpha() and not text.rstrip().endswith("?"):
            food_name = _name(text)
    if food_name and re.match(
        r"^(?:gì|gi|quán|quan|trong bán kính|trường|ở đâu|ngon|gần đây|chỗ ăn)\b", food_name, re.I
    ):
        food_name = None
    return FoodExtractionResult(food_name, place_name, preference)
