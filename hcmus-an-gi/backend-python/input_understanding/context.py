"""
context.py – Hợp nhất ngữ cảnh hội thoại qua các lượt (Multi-turn Context Management).

Quy tắc:
1. Duy trì và cập nhật thông tin món ăn (food_type, food_group, preference).
2. Tự động áp dụng giá trị mặc định cho ngân sách (DEFAULT_BUDGET = 30.000đ)
   và khoảng cách (DEFAULT_RADIUS_M = 3.000m) khi người dùng không cung cấp
   CHO CÁC INTENT TÌM KIẾM QUÁN (search_food, refine_search, recommendation).
3. KHÔNG áp dụng giá trị mặc định cho các intent không liên quan (pure emotion, other).
4. Phân biệt rõ giá trị do người dùng nhập và giá trị mặc định qua cờ:
   budget_is_default và radius_is_default.
5. Tuyệt đối không để giá trị mặc định ghi đè lên giá trị người dùng đã nhập.
6. Cảm xúc được lưu giữ và hết hạn sau EMOTION_TTL_TURNS lượt không được nhắc lại.
"""

from .config import DEFAULT_BUDGET, DEFAULT_RADIUS_M, EMOTION_TTL_TURNS


SEARCH_RELATED_INTENTS = {"search_food", "refine_search", "recommendation"}


def merge_context(previous: dict, extracted) -> dict:
    """
    Hợp nhất ngữ cảnh cũ (previous) với thông tin mới trích xuất (extracted).

    Parameters
    ----------
    previous : dict
        Ngữ cảnh từ các lượt trước.
    extracted : ExtractedIntent
        Kết quả trích xuất của lượt hiện tại.

    Returns
    -------
    dict
        Ngữ cảnh đã được cập nhật đầy đủ và chính xác.
    """
    result = previous.copy()
    data = extracted.model_dump()

    # Tăng bộ đếm lượt
    turn_count = result.get("turn_count", 0) + 1
    result["turn_count"] = turn_count

    # Xác định intent hiện tại
    current_intent = data.get("intent") or result.get("intent", "search_food")
    result["intent"] = current_intent

    # --- Cơ sở HCMUS (campus) ---
    if data.get("campus") is not None:
        result["campus"] = data["campus"]

    # --- Cuisine / Món ăn cũ ---
    if data.get("cuisine") is not None:
        result["cuisine"] = data["cuisine"]

    # --- Food Understanding: food_type, food_group, preference, food_info ---
    for food_key in ("food_type", "food_group", "preference", "food_info"):
        if data.get(food_key) is not None:
            result[food_key] = data[food_key]

    # --- Keywords: giữ cũ nếu lượt mới không có ---
    if data.get("keywords"):
        result["keywords"] = data["keywords"]
    elif "keywords" not in result:
        result["keywords"] = []

    # --- Ngân sách (budget) & Giá trị mặc định ---
    # Nếu lượt mới có ngân sách do người dùng cung cấp
    if data.get("budget") is not None:
        result["budget"] = data["budget"]
        result["budget_is_default"] = False  # Giá trị do người dùng nhập
    elif result.get("budget") is not None:
        # Giữ lại giá trị cũ (không ghi đè dù là do user nhập hay default cũ)
        pass
    else:
        # Chưa có ngân sách trong context: chỉ áp dụng mặc định nếu là intent tìm kiếm
        if current_intent in SEARCH_RELATED_INTENTS:
            result["budget"] = DEFAULT_BUDGET
            result["budget_is_default"] = True
        else:
            result["budget"] = None
            result["budget_is_default"] = False

    # --- Bán kính (radius_m) & Giá trị mặc định ---
    # Nếu lượt mới có bán kính do người dùng cung cấp
    if data.get("radius_m") is not None:
        result["radius_m"] = data["radius_m"]
        result["radius_is_default"] = False  # Giá trị do người dùng nhập
    elif result.get("radius_m") is not None:
        # Giữ lại giá trị cũ
        pass
    else:
        # Chưa có bán kính trong context: chỉ áp dụng mặc định nếu là intent tìm kiếm
        if current_intent in SEARCH_RELATED_INTENTS:
            result["radius_m"] = DEFAULT_RADIUS_M
            result["radius_is_default"] = True
        else:
            result["radius_m"] = None
            result["radius_is_default"] = False

    # --- Cảm xúc (Emotion Context & Aging) ---
    new_emotion = data.get("emotion")

    if new_emotion and new_emotion.get("category"):
        # Lượt này có cảm xúc mới → ghi đè
        result["emotion"] = new_emotion
        result["emotion_turn"] = turn_count
    else:
        # Không có cảm xúc mới → kiểm tra aging của cảm xúc cũ
        old_emotion_turn = result.get("emotion_turn")
        if old_emotion_turn is not None:
            age = turn_count - old_emotion_turn
            if age > EMOTION_TTL_TURNS:
                result["emotion"] = None
                result["emotion_turn"] = None

    # Nếu intent là tìm kiếm rõ ràng, reset cờ wants_food_suggestion để không hỏi lại
    if current_intent in ("search_food", "refine_search"):
        if result.get("emotion") and isinstance(result["emotion"], dict):
            result["emotion"]["wants_food_suggestion"] = False

    return result
