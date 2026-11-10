"""
tests/test_context.py

Kiểm tra context merging, emotion aging, và budget preservation.
Chạy: cd backend-python && python -m pytest tests/test_context.py -v
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from input_understanding.context import merge_context, EMOTION_TTL_TURNS
from input_understanding.schemas import ExtractedIntent, EmotionInfo


def make_extracted(**kwargs) -> ExtractedIntent:
    """Helper để tạo ExtractedIntent với giá trị mặc định."""
    defaults = {
        "intent": "search_food",
        "campus": None,
        "budget": None,
        "radius_m": None,
        "cuisine": None,
        "keywords": [],
        "emotion": None,
        "emotion_turn": None,
    }
    defaults.update(kwargs)
    return ExtractedIntent(**defaults)


def make_emotion(category: str, confidence: float = 0.9, wants_food: bool = True) -> EmotionInfo:
    return EmotionInfo(
        category=category,
        confidence=confidence,
        wants_food_suggestion=wants_food
    )


class TestMergeContextBasic:
    """Kiểm tra merge ngữ cảnh cơ bản."""

    def test_empty_previous(self):
        """Merge từ ngữ cảnh rỗng."""
        previous = {}
        extracted = make_extracted(campus="q5", budget=40000, radius_m=500)
        result = merge_context(previous, extracted)
        assert result["campus"] == "q5"
        assert result["budget"] == 40000
        assert result["radius_m"] == 500

    def test_keep_previous_campus_if_not_updated(self):
        """Giữ campus cũ khi không có campus mới."""
        previous = {"campus": "q5", "budget": 40000, "radius_m": 500}
        extracted = make_extracted(budget=60000)  # chỉ cập nhật budget
        result = merge_context(previous, extracted)
        assert result["campus"] == "q5"  # giữ cũ
        assert result["budget"] == 60000  # cập nhật mới

    def test_budget_preserved_when_not_mentioned(self):
        """Budget cũ không bị xóa khi người dùng chỉ nói về cảm xúc."""
        previous = {"campus": "q5", "budget": 40000, "radius_m": 500}
        extracted = make_extracted(
            intent="emotion_based_food_suggestion",
            emotion=make_emotion("stress")
        )
        result = merge_context(previous, extracted)
        assert result["budget"] == 40000  # giữ nguyên

    def test_budget_updated_when_new_value(self):
        """Budget được cập nhật khi người dùng nêu số mới."""
        previous = {"campus": "q5", "budget": 40000, "radius_m": 500}
        extracted = make_extracted(budget=60000)
        result = merge_context(previous, extracted)
        assert result["budget"] == 60000

    def test_null_does_not_overwrite_existing(self):
        """Giá trị None không ghi đè giá trị cũ."""
        previous = {"campus": "q5", "budget": 40000, "radius_m": 500}
        extracted = make_extracted(campus=None, budget=None, radius_m=None)
        result = merge_context(previous, extracted)
        assert result["campus"] == "q5"
        assert result["budget"] == 40000
        assert result["radius_m"] == 500

    def test_turn_count_increments(self):
        """turn_count tăng lên mỗi lượt."""
        previous = {"turn_count": 3}
        extracted = make_extracted()
        result = merge_context(previous, extracted)
        assert result["turn_count"] == 4

    def test_keywords_updated(self):
        """Keywords được cập nhật khi có từ khóa mới."""
        previous = {"keywords": ["cơm", "gà"]}
        extracted = make_extracted(keywords=["bún", "bò"])
        result = merge_context(previous, extracted)
        assert result["keywords"] == ["bún", "bò"]

    def test_keywords_kept_when_empty(self):
        """Keywords cũ được giữ khi lượt mới không có."""
        previous = {"keywords": ["cơm", "gà"]}
        extracted = make_extracted(keywords=[])
        result = merge_context(previous, extracted)
        assert result["keywords"] == ["cơm", "gà"]


class TestEmotionContext:
    """Kiểm tra emotion context merging và aging."""

    def test_emotion_stored_on_new_detection(self):
        """Cảm xúc mới được lưu vào context."""
        previous = {}
        extracted = make_extracted(
            intent="emotion_based_food_suggestion",
            emotion=make_emotion("sadness")
        )
        result = merge_context(previous, extracted)
        assert result["emotion"]["category"] == "sadness"
        assert result["emotion_turn"] == 1

    def test_emotion_preserved_across_turns(self):
        """Cảm xúc được giữ khi lượt sau không có cảm xúc mới."""
        previous = {
            "emotion": {"category": "stress", "confidence": 0.9, "wants_food_suggestion": True},
            "emotion_turn": 2,
            "turn_count": 2,
        }
        extracted = make_extracted(budget=40000)  # không có emotion mới
        result = merge_context(previous, extracted)
        assert result["emotion"]["category"] == "stress"

    def test_emotion_expires_after_ttl(self):
        """Cảm xúc bị xóa sau EMOTION_TTL_TURNS lượt không được nhắc lại."""
        previous = {
            "emotion": {"category": "sadness", "confidence": 0.9, "wants_food_suggestion": True},
            "emotion_turn": 1,
            "turn_count": 1 + EMOTION_TTL_TURNS,  # vừa đủ cũ
        }
        extracted = make_extracted()
        result = merge_context(previous, extracted)
        # Sau EMOTION_TTL_TURNS lượt → bị xóa
        assert result.get("emotion") is None

    def test_emotion_overwritten_by_new_emotion(self):
        """Cảm xúc cũ bị ghi đè bởi cảm xúc mới."""
        previous = {
            "emotion": {"category": "sadness", "confidence": 0.9, "wants_food_suggestion": True},
            "emotion_turn": 1,
            "turn_count": 2,
        }
        extracted = make_extracted(
            emotion=make_emotion("happiness", confidence=0.95)
        )
        result = merge_context(previous, extracted)
        assert result["emotion"]["category"] == "happiness"

    def test_search_food_clears_wants_food_suggestion(self):
        """Khi intent là search_food, wants_food_suggestion được reset."""
        previous = {
            "emotion": {"category": "stress", "confidence": 0.9, "wants_food_suggestion": True},
            "emotion_turn": 1,
            "turn_count": 1,
        }
        extracted = make_extracted(intent="search_food", campus="q5", budget=40000)
        result = merge_context(previous, extracted)
        # Emotion vẫn còn nhưng wants_food_suggestion = False
        assert result["emotion"]["wants_food_suggestion"] is False

    def test_emotion_not_set_when_message_unrelated(self):
        """Tin nhắn không liên quan không tạo emotion mới."""
        previous = {}
        extracted = make_extracted(intent="other", emotion=None)
        result = merge_context(previous, extracted)
        assert result.get("emotion") is None


class TestMultiTurnScenarios:
    """Kiểm tra các kịch bản hội thoại nhiều lượt."""

    def test_emotion_then_food_request(self):
        """
        Lượt 1: Người dùng bày tỏ cảm xúc
        Lượt 2: Người dùng yêu cầu gợi ý món
        """
        # Lượt 1
        previous = {}
        extracted1 = make_extracted(
            intent="emotion_based_food_suggestion",
            emotion=make_emotion("stress", wants_food=False)
        )
        ctx1 = merge_context(previous, extracted1)
        assert ctx1["emotion"]["category"] == "stress"

        # Lượt 2: người dùng hỏi về đồ ăn
        extracted2 = make_extracted(
            intent="emotion_based_food_suggestion",
            emotion=make_emotion("stress", wants_food=True)
        )
        ctx2 = merge_context(ctx1, extracted2)
        assert ctx2["emotion"]["wants_food_suggestion"] is True

    def test_budget_supplied_later(self):
        """
        Lượt 1: Chỉ có campus
        Lượt 2: Chỉ có budget
        Lượt 3: Chỉ có radius_m
        """
        ctx = {}
        ctx = merge_context(ctx, make_extracted(campus="q5"))
        assert ctx["campus"] == "q5"

        ctx = merge_context(ctx, make_extracted(budget=40000))
        assert ctx["campus"] == "q5"  # giữ
        assert ctx["budget"] == 40000

        ctx = merge_context(ctx, make_extracted(radius_m=500))
        assert ctx["campus"] == "q5"  # giữ
        assert ctx["budget"] == 40000  # giữ
        assert ctx["radius_m"] == 500

    def test_budget_updated_across_turns(self):
        """
        Người dùng đổi ngân sách ở lượt sau.
        """
        ctx = {"campus": "q5", "budget": 40000, "radius_m": 500}
        ctx = merge_context(ctx, make_extracted(budget=60000))
        assert ctx["budget"] == 60000

    def test_unrelated_message_does_not_reset_context(self):
        """
        Tin nhắn không liên quan không làm mất ngữ cảnh cũ.
        """
        ctx = {"campus": "q5", "budget": 40000, "radius_m": 500}
        # Tin nhắn kiểu "other"
        ctx = merge_context(ctx, make_extracted(intent="other"))
        assert ctx["campus"] == "q5"
        assert ctx["budget"] == 40000
        assert ctx["radius_m"] == 500
