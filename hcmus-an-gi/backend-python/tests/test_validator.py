"""
tests/test_validator.py

Kiểm tra validate_intent – đảm bảo budget được normalize trước khi validate.
Chạy: cd backend-python && python -m pytest tests/test_validator.py -v
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from input_understanding.schemas import ExtractedIntent, EmotionInfo
from input_understanding.validator import validate_intent


def make_intent(**kwargs) -> ExtractedIntent:
    defaults = {
        "intent": "search_food",
        "campus": None,
        "budget": None,
        "radius_m": None,
        "cuisine": None,
        "keywords": [],
        "emotion": None,
    }
    defaults.update(kwargs)
    return ExtractedIntent(**defaults)


class TestValidateBudget:
    """Kiểm tra validate_intent xử lý budget đúng cách."""

    def test_valid_budget_kept(self):
        """Budget hợp lệ trong khoảng → giữ nguyên."""
        intent = make_intent(budget=40000)
        result = validate_intent(intent)
        assert result.budget == 40000

    def test_budget_too_small_removed(self):
        """Budget < 5000 → xóa."""
        intent = make_intent(budget=100)
        result = validate_intent(intent)
        assert result.budget is None

    def test_budget_too_large_removed(self):
        """Budget > 2,000,000 → xóa."""
        intent = make_intent(budget=5_000_000)
        result = validate_intent(intent)
        assert result.budget is None

    def test_budget_at_min_boundary(self):
        """Budget = 5000 → hợp lệ."""
        intent = make_intent(budget=5000)
        result = validate_intent(intent)
        assert result.budget == 5000

    def test_budget_none_stays_none(self):
        """Budget None → vẫn là None."""
        intent = make_intent(budget=None)
        result = validate_intent(intent)
        assert result.budget is None


class TestValidateCampus:
    """Kiểm tra validate_intent xử lý campus."""

    def test_valid_campus_q5(self):
        intent = make_intent(campus="q5")
        result = validate_intent(intent)
        assert result.campus == "q5"

    def test_valid_campus_lang(self):
        intent = make_intent(campus="lang")
        result = validate_intent(intent)
        assert result.campus == "lang"

    def test_invalid_campus_removed(self):
        # Dùng model_construct để mô phỏng dữ liệu thô không hợp lệ
        intent = ExtractedIntent.model_construct(
            intent="search_food",
            campus="unknown_campus",
            budget=None,
            radius_m=None,
            cuisine=None,
            keywords=[],
            emotion=None,
        )
        result = validate_intent(intent)
        assert result.campus is None


class TestValidateEmotion:
    """Kiểm tra validate_intent xử lý emotion."""

    def test_high_confidence_emotion_kept(self):
        """Emotion với confidence cao → giữ."""
        emotion = EmotionInfo(category="sadness", confidence=0.9, wants_food_suggestion=True)
        intent = make_intent(emotion=emotion)
        result = validate_intent(intent)
        assert result.emotion is not None
        assert result.emotion.category == "sadness"

    def test_low_confidence_emotion_removed(self):
        """Emotion với confidence thấp → xóa."""
        emotion = EmotionInfo(category="stress", confidence=0.3, wants_food_suggestion=False)
        intent = make_intent(emotion=emotion)
        result = validate_intent(intent)
        assert result.emotion is None

    def test_emotion_at_threshold(self):
        """Emotion với confidence = 0.5 (threshold) → giữ."""
        emotion = EmotionInfo(category="tiredness", confidence=0.5)
        intent = make_intent(emotion=emotion)
        result = validate_intent(intent)
        assert result.emotion is not None

    def test_no_emotion_stays_none(self):
        """Không có emotion → vẫn là None."""
        intent = make_intent(emotion=None)
        result = validate_intent(intent)
        assert result.emotion is None
