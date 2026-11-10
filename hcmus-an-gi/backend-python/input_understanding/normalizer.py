"""
normalizer.py – Chuẩn hóa ngân sách VND từ các dạng ngôn ngữ tự nhiên.

Hỗ trợ các định dạng:
  200000        → 200000
  200k / 200K   → 200000
  200 K         → 200000
  200.000đ      → 200000  (dấu chấm phân cách hàng nghìn)
  200,000 VND   → 200000  (dấu phẩy phân cách hàng nghìn)
  200 nghìn     → 200000
  0.2 triệu     → 200000
  1 triệu       → 1000000
  1.5 triệu     → 1500000

Tất cả giá trị trả về dạng số nguyên VND (int) hoặc None nếu không hợp lệ.
"""

import re
from typing import Optional

# ---------------------------------------------------------------------------
# Các mẫu nhận diện đơn vị tiền tệ
# ---------------------------------------------------------------------------

_UNIT_K = re.compile(
    r"^(?:k|ngh[iì]n|ng[aà]n)$",
    re.IGNORECASE
)

_UNIT_M = re.compile(
    r"^(?:tri[eêệ]u|tr)$",
    re.IGNORECASE
)

_THOU_SEP_PATTERN = re.compile(
    r"^\d{1,3}(?:[.,]\d{3})+$"
)

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def normalize_budget(raw: object) -> Optional[int]:
    """
    Chuyển đổi một biểu diễn ngân sách đơn lẻ về số nguyên VND (int).

    Parameters
    ----------
    raw : str | int | float | None
        Giá trị ngân sách thô.

    Returns
    -------
    int | None
        Số nguyên VND, hoặc None nếu không xác định được.
    """
    if raw is None:
        return None

    # Nếu là int/float
    if isinstance(raw, (int, float)):
        v = int(raw)
        return v if v > 0 else None

    text = str(raw).strip()
    if not text or text.lower() in ("null", "none", "nan"):
        return None

    # Xóa ký hiệu tiền tệ ở cuối/đầu (vnd, vnđ, đ, ₫, đồng)
    text = re.sub(r"(?i)\b(?:vnd|vnđ|d|đ|đồng|dong)\b", "", text)
    text = re.sub(r"[₫đĐ]", "", text)
    text = text.strip()

    if not text:
        return None

    # Dạng dấu phân cách hàng nghìn rõ ràng: 200.000 hoặc 200,000 hoặc 1.000.000
    if _THOU_SEP_PATTERN.match(text):
        clean = re.sub(r"[.,]", "", text)
        try:
            return int(clean)
        except ValueError:
            return None

    # Tách số và đơn vị: e.g. "200k", "200 K", "1.5 triệu", "0.2 triệu", "200 nghìn"
    m = re.match(
        r"""
        ^
        (                           # nhóm 1: số
            \d+                     # phần nguyên
            (?:[.,]\d+)?            # phần thập phân (nếu có)
        )
        \s*                         # khoảng trắng tùy chọn
        (                           # nhóm 2: đơn vị
            [a-zA-ZàáảãạăằắẳẵặâầấẩẫậèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵđĐ]+
        )?
        $
        """,
        text,
        re.VERBOSE | re.UNICODE,
    )

    if not m:
        return None

    num_str = m.group(1).replace(",", ".")
    unit_str = (m.group(2) or "").strip().lower()

    try:
        num = float(num_str)
    except ValueError:
        return None

    if num <= 0:
        return None

    # Áp dụng đơn vị
    if unit_str:
        if _UNIT_M.match(unit_str):
            return int(round(num * 1_000_000))
        if _UNIT_K.match(unit_str):
            return int(round(num * 1_000))
        # Đơn vị không nhận biết được
        return None

    # Không có đơn vị:
    # - Nếu số < 10: có thể là số đếm, không tự suy đoán thành tiền
    # - Nếu 10 <= số < 1000: chuẩn người Việt nói "200" tức là 200k (200,000 VND)
    # - Nếu số >= 1000: số VND thực tế (ví dụ: "200000" → 200000 VND)
    if num < 10:
        return None
    if num < 1_000:
        return int(round(num * 1_000))
    return int(round(num))


def normalize_budget_text(text: str) -> Optional[int]:
    """
    Tìm và chuẩn hóa ngân sách trong một câu văn bản tự nhiên bất kỳ.

    Tránh nhận diện nhầm các số không phải tiền (như "quận 5", "2 người", "top 5").
    """
    if not text:
        return None

    cleaned = text.strip()
    # Nếu toàn bộ câu là một biểu thức ngân sách
    full_match = normalize_budget(cleaned)
    if full_match is not None and full_match >= 5_000:
        return full_match

    # Tìm trong câu văn bản theo các mẫu cụ thể
    # 1. Có từ khóa tiền tệ phía trước (dưới, tối đa, max, khoảng, tầm, giá, ngân sách, <)
    #    Ví dụ: "dưới 200k", "tối đa 35k", "ngân sách 200000 đồng", "khoảng 200 nghìn"
    prefix_pattern = re.compile(
        r"""
        (?:dưới|duoi|tối\s*đa|toi\s*da|max|khoảng|khoang|tầm|tam|giá|gia|ngân\s*sách|ngan\s*sach|<|<=)
        \s*
        (
            \d{1,3}(?:[.,]\d{3})+   # 200.000 / 200,000
            | \d+(?:[.,]\d+)?        # 200 / 1.5 / 200000
        )
        \s*
        (
            tri[eêệ]u|tr\b|k\b|ngh[iì]n|ng[aà]n|vnd|vnđ|đ|d\b|đồng
        )?
        """,
        re.IGNORECASE | re.VERBOSE
    )

    for m in prefix_pattern.finditer(cleaned):
        raw = m.group(1) + (" " + m.group(2) if m.group(2) else "")
        val = normalize_budget(raw.strip())
        if val is not None and val >= 5_000:
            return val

    # 2. Có đơn vị tiền tệ rõ ràng phía sau (k, nghìn, triệu, vnd, đ, ...)
    #    Ví dụ: "200k", "1.5 triệu", "200.000đ", "200,000 VND", "200 nghìn"
    suffix_pattern = re.compile(
        r"""
        \b
        (
            \d{1,3}(?:[.,]\d{3})+
            | \d+(?:[.,]\d+)?
        )
        \s*
        (
            tri[eêệ]u|tr\b|k\b|ngh[iì]n|ng[aà]n|vnd|vnđ|đ|đồng
        )
        \b
        """,
        re.IGNORECASE | re.VERBOSE
    )

    for m in suffix_pattern.finditer(cleaned):
        raw = m.group(1) + " " + m.group(2)
        val = normalize_budget(raw.strip())
        if val is not None and val >= 5_000:
            return val

    # 3. Số lớn độc lập biểu thị VND (>= 10000), có dấu phân cách hoặc số nguyên thuần
    #    Ví dụ: "ăn 200000 được không"
    large_number_pattern = re.compile(
        r"""
        (?<![a-zA-Z0-9_])
        (
            \d{1,3}(?:[.,]\d{3})+   # 200.000 hoặc 200,000
            | [1-9]\d{4,7}          # 10000 đến 99999999
        )
        (?![a-zA-Z0-9_])
        """,
        re.VERBOSE
    )

    for m in large_number_pattern.finditer(cleaned):
        # Tránh các số điện thoại hoặc mã
        val = normalize_budget(m.group(1))
        if val is not None and 5_000 <= val <= 2_000_000:
            return val

    return None
