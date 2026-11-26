from .config import (
    MIN_BUDGET,
    MAX_BUDGET,
    MIN_RADIUS_M,
    MAX_RADIUS_M,
    EMOTION_MIN_CONFIDENCE,
)
from .normalizer import normalize_budget


def validate_intent(data):
    """
    Kiểm tra và chuẩn hóa dữ liệu trích xuất từ Gemini:
    1. campus: chỉ cho phép q5 / lang
    2. budget: normalize qua normalizer rồi kiểm tra khoảng hợp lệ
    3. radius_m: kiểm tra khoảng hợp lệ
    4. emotion: chỉ giữ nếu confidence >= EMOTION_MIN_CONFIDENCE
    """

    # --- campus ---
    if data.campus not in (None, "q5", "lang"):
        data.campus = None

    # --- budget: normalize trước khi validate khoảng ---
    if data.budget is not None:
        normalized = normalize_budget(data.budget)
        if normalized is not None and MIN_BUDGET <= normalized <= MAX_BUDGET:
            data.budget = normalized
        else:
            data.budget = None

    # --- radius_m ---
    if data.radius_m is not None:
        if not MIN_RADIUS_M <= data.radius_m <= MAX_RADIUS_M:
            data.radius_m = None

    # --- emotion: bỏ nếu confidence quá thấp ---
    if data.emotion is not None:
        if data.emotion.confidence < EMOTION_MIN_CONFIDENCE or data.emotion.category is None:
            data.emotion = None

    return data
