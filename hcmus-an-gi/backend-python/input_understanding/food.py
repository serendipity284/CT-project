"""
food.py – Chuẩn hóa và xử lý thông tin món ăn (Food Understanding).

Không sử dụng danh sách liệt kê cứng (hardcoded dictionary).
Hệ thống sử dụng Gemini LLM để nhận diện tên món, nhóm món và sở thích;
module này chịu trách nhiệm:
1. Thuật toán slugify động: chuyển bất kỳ tên món tiếng Việt sang canonical slug.
2. Bóc tách từ khóa tìm kiếm động để truy vấn cơ sở dữ liệu (places.cuisine, places.name).
3. Fallback bóc tách nhẹ khi mất kết nối Gemini (dựa trên cấu trúc ngữ pháp tiếng Việt).
"""

import re
import unicodedata
from typing import Optional, NamedTuple


class FoodExtractionResult(NamedTuple):
    food_type: Optional[str]
    food_name: Optional[str]
    food_group: Optional[str]
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


def extract_search_keywords(food_name: Optional[str], food_type: Optional[str] = None) -> list[str]:
    """
    Trích xuất động các từ khóa tìm kiếm để khớp vào places.cuisine và places.name trong MySQL.

    Không dùng mapping tĩnh; phân tích trực tiếp từ food_name và food_type:
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

    if food_type:
        parts = food_type.split("_")
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

_FOOD_VERB_PATTERN = re.compile(
    r"""
    (?:
        mu[oố]n\s+[aă]n
        | t[iì]m(?:\s+(?:qu[aá]n|m[oó]n|d[oồ]))?
        | qu[aá]n
        | [aă]n
        | th[eè]m
        | g[oợ]i\s+[yý]\s+m[oó]n
        | d[oổ]i\s+sang
    )
    \s+
    ([a-zA-ZàáảãạăằắẳẵặâầấẩẫậèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵđĐ\s]{2,30})
    """,
    re.IGNORECASE | re.VERBOSE,
)

_STOPWORDS = {
    "o", "ở", "tai", "tại", "gan", "gần", "truong", "trường",
    "duoi", "dưới", "tam", "tầm", "khoang", "khoảng",
    "gia", "giá", "ngan", "ngân", "sach", "sách", "cho",
    "q5", "lang", "quan 5", "quận 5", "lang dai hoc", "làng đại học",
    "khong", "không", "gi", "gì", "nao", "nào", "di", "đi", "nhe", "nhé",
}


def fallback_extract_food(text: str) -> FoodExtractionResult:
    """
    Trích xuất món ăn dự phòng dựa trên cấu trúc câu khi không có Gemini.
    Không bị giới hạn bởi danh sách món liệt kê.
    """
    if not text:
        return FoodExtractionResult(None, None, None, None)

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

    # Nhận diện nhóm món cơ bản nếu có trong câu
    food_group = None
    if "món nước" in lower or "mon nuoc" in lower:
        food_group = "mon_nuoc"
    elif "đồ chiên" in lower or "do chien" in lower:
        food_group = "do_chien"
    elif "đồ nướng" in lower or "do nuong" in lower:
        food_group = "do_nuong"
    elif "ăn vặt" in lower or "an vat" in lower:
        food_group = "do_an_vat"
    elif "đồ uống" in lower or "do uong" in lower or "nước uống" in lower or "nuoc uong" in lower:
        food_group = "do_uong"

    # Trích xuất cụm danh từ món ăn
    food_name = None
    food_type = None

    m = _FOOD_VERB_PATTERN.search(text)
    if m:
        candidate = m.group(1).strip()
        tokens = candidate.split()
        clean_tokens = []
        for tok in tokens:
            if tok.lower() in _STOPWORDS:
                break
            if any(c.isdigit() for c in tok):
                break
            clean_tokens.append(tok)

        if clean_tokens:
            cand_name = " ".join(clean_tokens)
            # Nếu cụm từ không đơn thuần là tên nhóm món
            if cand_name.lower() not in ("nước", "món nước", "đồ chiên", "đồ nướng", "ăn vặt", "đồ ăn vặt"):
                food_name = cand_name
                food_type = slugify_food(food_name)

    return FoodExtractionResult(
        food_type=food_type,
        food_name=food_name,
        food_group=food_group,
        preference=preference,
    )
