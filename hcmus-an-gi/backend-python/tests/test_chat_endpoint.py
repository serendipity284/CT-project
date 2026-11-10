"""
tests/test_chat_endpoint.py

Kiểm tra API endpoint /chat của FastAPI:
- Nhận diện ngân sách 200000 và các định dạng qua fallback regex & normalizer
- Các trường hợp cảm xúc (Sadness, Stress, Tiredness, Happiness, Celebration, Boredom, Comfort)
- Ngữ cảnh đa lượt (Multi-turn context management)
- Không ghi đè ngân sách hợp lệ
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from unittest.mock import patch
import pytest
from fastapi.testclient import TestClient
from app import app
from input_understanding.schemas import ExtractedIntent, EmotionInfo

client = TestClient(app)


# ---------------------------------------------------------------------------
# PHẦN 1: TEST BUDGET RECOGNITION QUA /chat
# ---------------------------------------------------------------------------

class TestChatBudgetRecognition:
    """Kiểm tra nhận diện ngân sách qua endpoint /chat."""

    @pytest.mark.parametrize("msg,expected_budget", [
        ("ngân sách 200000", 200000),
        ("quận 5, dưới 200000, 500m", 200000),
        ("dưới 200k", 200000),
        ("dưới 200 K", 200000),
        ("ăn dưới 200.000đ", 200000),
        ("tầm 200,000 VND", 200000),
        ("khoảng 200 nghìn", 200000),
        ("khoảng 0.2 triệu", 200000),
        ("dưới 1 triệu", 1000000),
        ("ăn tầm 1.5 triệu", 1500000),
    ])
    def test_budget_formats_via_fallback(self, msg, expected_budget):
        """Khi Gemini không khả dụng (hoặc lỗi), fallback regex dùng normalizer nhận diện chính xác."""
        with patch("app.extract_intent", side_effect=Exception("No API key / network")):
            res = client.post("/chat", json={"message": msg, "campus": "q5", "radius_m": 500})
            assert res.status_code == 200
            data = res.json()
            assert data["budget"] == expected_budget

    def test_plain_200000_input(self):
        """Tin nhắn chỉ có đúng '200000'."""
        with patch("app.extract_intent", side_effect=Exception("No API key")):
            res = client.post("/chat", json={"message": "200000", "campus": "q5"})
            assert res.status_code == 200
            data = res.json()
            assert data["budget"] == 200000

    def test_existing_budget_not_overwritten_by_unrelated(self):
        """Ngân sách cũ không bị ghi đè bởi tin nhắn không chứa ngân sách."""
        with patch("app.extract_intent", side_effect=Exception("No API key")):
            res = client.post("/chat", json={
                "message": "quán nào gần trường?",
                "campus": "q5",
                "budget": 200000,
                "radius_m": 500
            })
            assert res.status_code == 200
            data = res.json()
            assert data["budget"] == 200000


# ---------------------------------------------------------------------------
# PHẦN 2: TEST EMOTION RECOGNITION QUA /chat
# ---------------------------------------------------------------------------

class TestChatEmotionCases:
    """Kiểm tra các trường hợp cảm xúc theo Case A - E."""

    def test_case_a_sadness_with_food_intent(self):
        """Case A: Buồn + muốn ăn gì đó → gợi ý món ấm áp, empathetic."""
        mock_intent = ExtractedIntent(
            intent="emotion_based_food_suggestion",
            emotion=EmotionInfo(category="sadness", confidence=0.92, wants_food_suggestion=True)
        )
        with patch("app.extract_intent", return_value=mock_intent):
            res = client.post("/chat", json={"message": "Hôm nay tôi buồn quá, muốn ăn gì đó cho vui."})
            assert res.status_code == 200
            data = res.json()
            assert data["emotion"]["category"] == "sadness"
            assert "buồn" in data["reply"].lower() or "cháo" in data["reply"].lower() or "ấm áp" in data["reply"].lower()
            assert data["ready"] is False  # Chưa chọn cơ sở / ngân sách

    def test_case_b_stress_food_intent(self):
        """Case B: Stress vì deadline → gợi ý nhẹ nhàng nạp năng lượng."""
        mock_intent = ExtractedIntent(
            intent="emotion_based_food_suggestion",
            emotion=EmotionInfo(category="stress", confidence=0.90, wants_food_suggestion=True)
        )
        with patch("app.extract_intent", return_value=mock_intent):
            res = client.post("/chat", json={"message": "Tôi đang stress vì deadline, muốn ăn gì đó."})
            assert res.status_code == 200
            data = res.json()
            assert data["emotion"]["category"] == "stress"
            assert "deadline" in data["reply"].lower() or "stress" in data["reply"].lower()

    def test_case_c_celebration_happiness(self):
        """Case C: Thi xong muốn tự thưởng → gợi ý ăn ngon."""
        mock_intent = ExtractedIntent(
            intent="emotion_based_food_suggestion",
            emotion=EmotionInfo(category="celebration", confidence=0.95, wants_food_suggestion=True)
        )
        with patch("app.extract_intent", return_value=mock_intent):
            res = client.post("/chat", json={"message": "Tôi vừa hoàn thành bài thi, muốn tự thưởng."})
            assert res.status_code == 200
            data = res.json()
            assert data["emotion"]["category"] == "celebration"
            assert "chúc mừng" in data["reply"].lower() or "đặc sản" in data["reply"].lower() or "xứng đáng" in data["reply"].lower()

    def test_case_d_emotion_without_explicit_food_intent(self):
        """Case D: Cảm xúc thuần túy không nhắc đến đồ ăn → đồng cảm, hỏi thăm nhẹ nhàng."""
        mock_intent = ExtractedIntent(
            intent="emotion_based_food_suggestion",
            emotion=EmotionInfo(category="sadness", confidence=0.88, wants_food_suggestion=False)
        )
        with patch("app.extract_intent", return_value=mock_intent):
            res = client.post("/chat", json={"message": "Hôm nay tôi buồn quá."})
            assert res.status_code == 200
            data = res.json()
            assert data["emotion"]["category"] == "sadness"
            assert data["ready"] is False
            # Phản hồi nhẹ nhàng, không bắt ép tìm quán ngay
            assert "buồn" in data["reply"].lower()

    def test_case_e_explicit_search_combined_with_emotion(self):
        """Case E: Yêu cầu tìm quán cụ thể kèm cảm xúc → ưu tiên tìm quán và ready khi đủ thông tin."""
        mock_intent = ExtractedIntent(
            intent="search_food",
            campus="q5",
            budget=40000,
            radius_m=800,
            cuisine="cháo",
            keywords=["cháo"],
            emotion=EmotionInfo(category="tiredness", confidence=0.85, wants_food_suggestion=False)
        )
        with patch("app.extract_intent", return_value=mock_intent):
            res = client.post("/chat", json={
                "message": "Tôi đang mệt, tìm cho tôi một quán cháo gần trường dưới 40k."
            })
            assert res.status_code == 200
            data = res.json()
            assert data["ready"] is True
            assert data["campus"] == "q5"
            assert data["budget"] == 40000
            assert data["radius_m"] == 800
            assert data["emotion"]["category"] == "tiredness"

    def test_boredom_case(self):
        """Chán ăn cơm, muốn đổi món."""
        mock_intent = ExtractedIntent(
            intent="emotion_based_food_suggestion",
            emotion=EmotionInfo(category="boredom", confidence=0.90, wants_food_suggestion=True)
        )
        with patch("app.extract_intent", return_value=mock_intent):
            res = client.post("/chat", json={"message": "Tôi chán ăn cơm rồi, muốn đổi món."})
            assert res.status_code == 200
            data = res.json()
            assert data["emotion"]["category"] == "boredom"
            assert "đổi" in data["reply"].lower() or "chán" in data["reply"].lower() or "bún" in data["reply"].lower()

    def test_neutral_message(self):
        """Tin nhắn trung tính, không cảm xúc."""
        mock_intent = ExtractedIntent(
            intent="search_food",
            campus="q5",
            budget=50000,
            radius_m=500,
            emotion=None
        )
        with patch("app.extract_intent", return_value=mock_intent):
            res = client.post("/chat", json={"message": "Quận 5, dưới 50k, 500m"})
            assert res.status_code == 200
            data = res.json()
            assert data["emotion"] is None
            assert data["ready"] is True


# ---------------------------------------------------------------------------
# PHẦN 3: TEST MULTI-TURN CONTEXT MANAGEMENT QUA /chat
# ---------------------------------------------------------------------------

class TestChatMultiTurnContext:
    """Kiểm tra quản lý ngữ cảnh qua nhiều lượt hội thoại liên tiếp."""

    def test_three_turn_flow(self):
        """
        Lượt 1: User: "Hôm nay tôi stress quá."
        Lượt 2: User: "Gợi ý cho tôi món gì ăn đi."
        Lượt 3: User: "Tìm quán cháo dưới 40k ở Quận 5 trong 500m."
        """
        # Turn 1
        mock_turn1 = ExtractedIntent(
            intent="emotion_based_food_suggestion",
            emotion=EmotionInfo(category="stress", confidence=0.92, wants_food_suggestion=False)
        )
        with patch("app.extract_intent", return_value=mock_turn1):
            res1 = client.post("/chat", json={"message": "Hôm nay tôi stress quá."})
            data1 = res1.json()
            assert data1["emotion"]["category"] == "stress"
            assert data1["ready"] is False

        # Turn 2: Frontend gửi lại emotion từ Turn 1
        mock_turn2 = ExtractedIntent(
            intent="emotion_based_food_suggestion",
            emotion=EmotionInfo(category="stress", confidence=0.92, wants_food_suggestion=True)
        )
        with patch("app.extract_intent", return_value=mock_turn2):
            res2 = client.post("/chat", json={
                "message": "Gợi ý cho tôi món gì ăn đi.",
                "emotion": data1["emotion"],
                "emotion_turn": data1["emotion_turn"],
                "turn_count": data1["turn_count"],
            })
            data2 = res2.json()
            assert data2["emotion"]["category"] == "stress"
            assert data2["ready"] is False

        # Turn 3: User cung cấp đầy đủ thông tin tìm kiếm
        mock_turn3 = ExtractedIntent(
            intent="search_food",
            campus="q5",
            budget=40000,
            radius_m=500,
            cuisine="cháo",
            keywords=["cháo"],
            emotion=None  # không nhắc lại cảm xúc
        )
        with patch("app.extract_intent", return_value=mock_turn3):
            res3 = client.post("/chat", json={
                "message": "Tìm quán cháo dưới 40k ở Quận 5 trong 500m.",
                "emotion": data2["emotion"],
                "emotion_turn": data2["emotion_turn"],
                "turn_count": data2["turn_count"],
            })
            data3 = res3.json()
            assert data3["ready"] is True
            assert data3["campus"] == "q5"
            assert data3["budget"] == 40000
            assert data3["radius_m"] == 500
            # Cảm xúc stress vẫn được lưu giữ trong background context
            assert data3["emotion"] is not None
            assert data3["emotion"]["category"] == "stress"
