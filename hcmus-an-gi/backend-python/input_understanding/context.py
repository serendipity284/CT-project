"""Hợp nhất món, quán, bộ lọc và cảm xúc qua các lượt chat."""

import json
import re
from pathlib import Path

from .config import EMOTION_TTL_TURNS


_patterns = json.loads(Path(__file__).with_name("unlimited_patterns.json").read_text())
UNLIMITED_PATTERNS = {key: re.compile(pattern) for key, pattern in _patterns.items()}


def merge_limits(result, data):
    for key, prefix in (("budget", "budget"), ("radius_m", "radius")):
        unlimited = f"{prefix}_unlimited"
        defaulted = f"{prefix}_is_default"
        if data.get(unlimited):
            result.update({key: None, unlimited: True, defaulted: False})
        elif data.get(key) is not None:
            result.update({key: data[key], unlimited: False, defaulted: False})
        elif result.get(unlimited) or result.get(key) is None or result.get(defaulted):
            result.update({key: None, unlimited: True, defaulted: False})



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

    # --- Food Understanding: food_name, place_name, preference ---
    for food_key in ("food_name", "place_name", "preference"):
        if data.get(food_key) is not None:
            result[food_key] = data[food_key]

    # --- Keywords: giữ cũ nếu lượt mới không có ---
    if data.get("keywords"):
        result["keywords"] = data["keywords"]
    elif "keywords" not in result:
        result["keywords"] = []

    merge_limits(result, data)

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
