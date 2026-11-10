"""
tests/test_food.py

Kiểm tra Food Understanding động (không hardcode dictionary) và
quản lý giá trị mặc định cho ngân sách & khoảng cách.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from input_understanding.food import slugify_food, extract_search_keywords, fallback_extract_food
from input_understanding.config import DEFAULT_BUDGET, DEFAULT_RADIUS_M
from input_understanding.schemas import ExtractedIntent, EmotionInfo
from input_understanding.context import merge_context
from input_understanding.validator import validate_intent


# ---------------------------------------------------------------------------
# PHẦN 1: TEST SLUGIFY DYNAMIC FOOD NAMES
# ---------------------------------------------------------------------------

class TestSlugifyFood:
    """Kiểm tra thuật toán slugify động không phụ thuộc danh sách liệt kê."""

    @pytest.mark.parametrize("food_input,expected_slug", [
        ("Cơm tấm", "com_tam"),
        ("cơm tấm", "com_tam"),
        ("Phở", "pho"),
        ("phở bò", "pho_bo"),
        ("Bún bò", "bun_bo"),
        ("Bún bò Huế", "bun_bo_hue"),
        ("Bánh mì", "banh_mi"),
        ("Hủ tiếu", "hu_tieu"),
        ("Cháo", "chao"),
        # Các món mới hoàn toàn (chưa từng liệt kê)
        ("Bánh mì chảo", "banh_mi_chao"),
        ("Takoyaki", "takoyaki"),
        ("Mì cay 7 cấp độ", "mi_cay_7_cap_do"),
        ("Cơm sườn non nướng", "com_suon_non_nuong"),
        ("Trà mãng cầu", "tra_mang_cau"),
    ])
    def test_dynamic_slugify(self, food_input, expected_slug):
        assert slugify_food(food_input) == expected_slug

    def test_empty_or_none(self):
        assert slugify_food(None) is None
        assert slugify_food("") is None
        assert slugify_food("   ") is None


# ---------------------------------------------------------------------------
# PHẦN 2: TEST EXTRACT SEARCH KEYWORDS CHO DATABASE
# ---------------------------------------------------------------------------

class TestExtractSearchKeywords:
    """Kiểm tra tạo từ khóa truy vấn MySQL places."""

    def test_com_tam_keywords(self):
        keywords = extract_search_keywords("Cơm tấm", "com_tam")
        assert "cơm tấm" in [k.lower() for k in keywords]
        assert "cơm" in [k.lower() for k in keywords]
        assert "tấm" in [k.lower() for k in keywords]

    def test_pho_bo_keywords(self):
        keywords = extract_search_keywords("Phở bò", "pho_bo")
        assert "phở bò" in [k.lower() for k in keywords]
        assert "phở" in [k.lower() for k in keywords]

    def test_new_dish_keywords(self):
        """Món mới bất kỳ vẫn trích xuất được từ khóa tìm kiếm."""
        keywords = extract_search_keywords("Bánh mì chảo", "banh_mi_chao")
        assert "bánh mì chảo" in [k.lower() for k in keywords]
        assert "bánh" in [k.lower() for k in keywords]


# ---------------------------------------------------------------------------
# PHẦN 3: TEST FALLBACK EXTRACT FOOD (NGỮ PHÁP TIẾNG VIỆT)
# ---------------------------------------------------------------------------

class TestFallbackExtractFood:
    """Kiểm tra trích xuất món ăn dựa trên ngữ pháp khi không có Gemini."""

    def test_tim_quan_com_tam(self):
        res = fallback_extract_food("Tìm quán cơm tấm ở Quận 5")
        assert res.food_type == "com_tam"
        assert res.food_name == "cơm tấm"

    def test_toi_muon_an_pho(self):
        res = fallback_extract_food("Tôi muốn ăn phở")
        assert res.food_type == "pho"

    def test_tim_quan_bun_bo(self):
        res = fallback_extract_food("Tìm quán bún bò dưới 40k")
        assert res.food_type == "bun_bo"

    def test_preference_cay(self):
        res = fallback_extract_food("Tìm quán mì cay")
        assert res.preference == "cay"

    def test_preference_khong_cay(self):
        res = fallback_extract_food("Tìm quán phở không cay")
        assert res.preference == "khong_cay"

    def test_food_group_mon_nuoc(self):
        res = fallback_extract_food("Tìm món nước ở quận 5")
        assert res.food_group == "mon_nuoc"


# ---------------------------------------------------------------------------
# PHẦN 4: TEST GIÁ TRỊ MẶC ĐỊNH VÀ CONTEXT MANAGEMENT
# ---------------------------------------------------------------------------

class TestDefaultsAndContext:
    """Kiểm tra áp dụng DEFAULT_BUDGET (30k) và DEFAULT_RADIUS_M (3km)."""

    def test_search_intent_applies_defaults_when_omitted(self):
        """Intent tìm kiếm quán tự động áp dụng giá trị mặc định khi người dùng không cung cấp."""
        previous = {}
        extracted = ExtractedIntent(
            intent="search_food",
            campus="q5",
            food_type="com_tam",
            budget=None,
            radius_m=None,
        )
        ctx = merge_context(previous, extracted)
        assert ctx["campus"] == "q5"
        assert ctx["food_type"] == "com_tam"
        assert ctx["budget"] == DEFAULT_BUDGET          # 30,000 VND
        assert ctx["budget_is_default"] is True
        assert ctx["radius_m"] == DEFAULT_RADIUS_M      # 3,000 mét
        assert ctx["radius_is_default"] is True

    def test_user_provided_budget_and_radius_override_defaults(self):
        """Nếu người dùng chỉ định thì ưu tiên giá trị của người dùng."""
        previous = {}
        extracted = ExtractedIntent(
            intent="search_food",
            campus="q5",
            budget=45000,
            radius_m=800,
        )
        ctx = merge_context(previous, extracted)
        assert ctx["budget"] == 45000
        assert ctx["budget_is_default"] is False
        assert ctx["radius_m"] == 800
        assert ctx["radius_is_default"] is False

    def test_non_search_intent_does_not_apply_defaults(self):
        """Intent không liên quan đến tìm kiếm (ví dụ pure emotion) KHÔNG áp dụng mặc định."""
        previous = {}
        extracted = ExtractedIntent(
            intent="emotion_based_food_suggestion",
            emotion=EmotionInfo(category="sadness", confidence=0.9, wants_food_suggestion=False),
            budget=None,
            radius_m=None,
        )
        ctx = merge_context(previous, extracted)
        assert ctx["budget"] is None
        assert ctx["radius_m"] is None

    def test_three_turn_scenario_from_user_prompt(self):
        """
        Kiểm tra chính xác kịch bản 3 lượt trong yêu cầu:
        Lượt 1: 'Tìm quán cơm tấm ở Quận 5.'
          -> food_type = com_tam, campus = q5, budget = 30000 (default), radius_m = 3000 (default)
        Lượt 2: 'Tăng ngân sách lên 50k.'
          -> budget = 50000 (user-provided), các thông tin khác giữ nguyên.
        Lượt 3: 'Tìm trong bán kính 5km.'
          -> radius_m = 5000 (user-provided), các thông tin khác giữ nguyên.
        """
        # Turn 1
        turn1_extracted = ExtractedIntent(
            intent="search_food",
            campus="q5",
            food_type="com_tam",
            budget=None,
            radius_m=None,
        )
        ctx1 = merge_context({}, turn1_extracted)
        assert ctx1["food_type"] == "com_tam"
        assert ctx1["campus"] == "q5"
        assert ctx1["budget"] == 30000
        assert ctx1["budget_is_default"] is True
        assert ctx1["radius_m"] == 3000
        assert ctx1["radius_is_default"] is True

        # Turn 2: 'Tăng ngân sách lên 50k'
        turn2_extracted = ExtractedIntent(
            intent="refine_search",
            budget=50000,
            campus=None,
            food_type=None,
            radius_m=None,
        )
        ctx2 = merge_context(ctx1, turn2_extracted)
        assert ctx2["food_type"] == "com_tam"           # giữ nguyên
        assert ctx2["campus"] == "q5"                   # giữ nguyên
        assert ctx2["budget"] == 50000                  # cập nhật giá trị mới của user
        assert ctx2["budget_is_default"] is False       # không còn là default
        assert ctx2["radius_m"] == 3000                 # giữ nguyên default cũ
        assert ctx2["radius_is_default"] is True

        # Turn 3: 'Tìm trong bán kính 5km'
        turn3_extracted = ExtractedIntent(
            intent="refine_search",
            radius_m=5000,
            budget=None,
            campus=None,
            food_type=None,
        )
        ctx3 = merge_context(ctx2, turn3_extracted)
        assert ctx3["food_type"] == "com_tam"           # giữ nguyên
        assert ctx3["campus"] == "q5"                   # giữ nguyên
        assert ctx3["budget"] == 50000                  # giữ nguyên giá trị user đã nhập ở Turn 2
        assert ctx3["budget_is_default"] is False
        assert ctx3["radius_m"] == 5000                 # cập nhật giá trị mới của user
        assert ctx3["radius_is_default"] is False

    def test_default_does_not_overwrite_user_budget(self):
        """Tuyệt đối không để giá trị mặc định ghi đè lên thông tin người dùng đã cung cấp."""
        ctx = {
            "campus": "q5",
            "budget": 60000,
            "budget_is_default": False,
            "radius_m": 500,
            "radius_is_default": False,
            "food_type": "pho",
        }
        # Người dùng gửi tin nhắn đổi món: "Đổi sang bún bò" (không nhắc lại budget)
        turn_extracted = ExtractedIntent(
            intent="refine_search",
            food_type="bun_bo",
            budget=None,
            radius_m=None,
        )
        new_ctx = merge_context(ctx, turn_extracted)
        assert new_ctx["food_type"] == "bun_bo"
        assert new_ctx["budget"] == 60000               # Vẫn là 60000, không bị hạ về 30000 default!
        assert new_ctx["budget_is_default"] is False
        assert new_ctx["radius_m"] == 500               # Vẫn là 500, không bị tăng lên 3000 default!
        assert new_ctx["radius_is_default"] is False
