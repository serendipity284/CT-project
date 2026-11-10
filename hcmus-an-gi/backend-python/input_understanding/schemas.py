from typing import Optional, Literal
from pydantic import BaseModel, Field


class EmotionInfo(BaseModel):
    """Thông tin cảm xúc được nhận diện từ tin nhắn của người dùng."""

    category: Optional[Literal[
        "sadness",       # buồn, thất vọng, cô đơn
        "stress",        # căng thẳng, áp lực, deadline
        "tiredness",     # mệt mỏi, kiệt sức
        "happiness",     # vui vẻ, phấn khích
        "celebration",   # muốn tự thưởng, ăn mừng
        "boredom",       # chán, muốn đổi món
        "comfort",       # muốn ăn gì đó ấm áp, dễ chịu
        "neutral",       # không rõ hoặc không có cảm xúc đặc biệt
    ]] = None

    confidence: float = Field(default=0.0, ge=0.0, le=1.0)

    # True nếu người dùng có ý muốn được gợi ý món ăn dựa trên cảm xúc
    wants_food_suggestion: bool = False


class FoodInfo(BaseModel):
    """Thông tin món ăn chi tiết (Food Understanding)."""

    food_type: Optional[str] = None      # canonical slug: com_tam, pho, bun_bo, chao, v.v.
    food_name: Optional[str] = None      # Tên hiển thị: Cơm tấm, Phở, Bún bò
    food_group: Optional[str] = None     # Nhóm món: mon_nuoc, do_chien, do_nuong, do_an_vat, mon_chay
    preference: Optional[str] = None     # Sở thích: cay, khong_cay, chay, thanh_dam


class ExtractedIntent(BaseModel):
    intent: Literal[
        "search_food",                    # tìm kiếm quán/món cụ thể
        "refine_search",                  # tinh chỉnh tìm kiếm đang có
        "recommendation",                 # gợi ý chung
        "emotion_based_food_suggestion",  # gợi ý dựa trên cảm xúc
        "other"                           # không rõ ý định
    ] = "search_food"

    campus: Optional[Literal["q5", "lang"]] = None

    # Ngân sách (VND)
    budget: Optional[int] = None
    budget_is_default: bool = False

    # Khoảng cách (mét)
    radius_m: Optional[int] = None
    radius_is_default: bool = False

    # Food Understanding
    food_type: Optional[str] = None      # slug chuẩn hóa (com_tam, pho, bun_bo, v.v.)
    food_group: Optional[str] = None     # nhóm món (mon_nuoc, do_chien, do_nuong, do_an_vat)
    preference: Optional[str] = None     # sở thích (cay, khong_cay, chay, thanh_dam)
    food_info: Optional[FoodInfo] = None

    cuisine: Optional[str] = None
    keywords: list[str] = Field(default_factory=list)

    # Cảm xúc
    emotion: Optional[EmotionInfo] = None
    emotion_turn: Optional[int] = None
