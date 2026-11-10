"""
tests/test_normalizer.py

Kiểm tra unit test cho normalizer.normalize_budget và normalize_budget_text.
Chạy: cd backend-python && python -m pytest tests/test_normalizer.py -v
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from input_understanding.normalizer import normalize_budget, normalize_budget_text


# ---------------------------------------------------------------------------
# normalize_budget – số / chuỗi đơn thuần
# ---------------------------------------------------------------------------

class TestNormalizeBudget:
    """Kiểm tra normalize_budget với các dạng đầu vào."""

    # --- Số nguyên thuần túy ---
    def test_plain_integer_200000(self):
        """200000 → 200000 (không nhân thêm)"""
        assert normalize_budget(200000) == 200000

    def test_plain_integer_50000(self):
        assert normalize_budget(50000) == 50000

    def test_plain_integer_35000(self):
        assert normalize_budget(35000) == 35000

    # --- Dạng k / K ---
    def test_200k_lowercase(self):
        assert normalize_budget("200k") == 200000

    def test_200K_uppercase(self):
        assert normalize_budget("200K") == 200000

    def test_200_K_space(self):
        """200 K (có khoảng trắng)"""
        assert normalize_budget("200 K") == 200000

    def test_35k(self):
        assert normalize_budget("35k") == 35000

    def test_40k(self):
        assert normalize_budget("40k") == 40000

    # --- Dạng dấu chấm/phẩy phân cách hàng nghìn ---
    def test_200_dot_000_vnd(self):
        """200.000đ → 200000"""
        assert normalize_budget("200.000đ") == 200000

    def test_200_comma_000_VND(self):
        """200,000 VND → 200000"""
        assert normalize_budget("200,000 VND") == 200000

    def test_1_dot_000_dot_000(self):
        """1.000.000 → 1000000"""
        assert normalize_budget("1.000.000") == 1000000

    # --- Dạng nghìn / ngàn ---
    def test_200_nghin(self):
        assert normalize_budget("200 nghìn") == 200000

    def test_200_ngan(self):
        assert normalize_budget("200 ngàn") == 200000

    def test_50_nghin(self):
        assert normalize_budget("50 nghìn") == 50000

    # --- Dạng triệu ---
    def test_02_trieu(self):
        """0.2 triệu → 200000"""
        assert normalize_budget("0.2 triệu") == 200000

    def test_1_trieu(self):
        """1 triệu → 1000000"""
        assert normalize_budget("1 triệu") == 1000000

    def test_1_5_trieu(self):
        """1.5 triệu → 1500000"""
        assert normalize_budget("1.5 triệu") == 1500000

    def test_2_trieu(self):
        assert normalize_budget("2 triệu") == 2000000

    def test_1_5_tr_abbr(self):
        """1.5tr → 1500000"""
        assert normalize_budget("1.5tr") == 1500000

    # --- Heuristic: số nhỏ không có đơn vị ---
    def test_small_number_heuristic(self):
        """200 (không đơn vị, < 1000) → 200000"""
        assert normalize_budget("200") == 200000

    def test_small_number_35(self):
        """35 → 35000"""
        assert normalize_budget("35") == 35000

    # --- Số thực Gemini trả về ---
    def test_float_200000(self):
        assert normalize_budget(200000.0) == 200000

    # --- None / invalid ---
    def test_none_input(self):
        assert normalize_budget(None) is None

    def test_zero_input(self):
        assert normalize_budget(0) is None

    def test_negative(self):
        assert normalize_budget(-1) is None

    def test_null_string(self):
        assert normalize_budget("null") is None

    def test_empty_string(self):
        assert normalize_budget("") is None

    def test_non_numeric(self):
        assert normalize_budget("abc") is None


# ---------------------------------------------------------------------------
# normalize_budget_text – tìm trong câu tự nhiên
# ---------------------------------------------------------------------------

class TestNormalizeBudgetText:
    """Kiểm tra normalize_budget_text – tìm ngân sách trong câu hội thoại."""

    def test_duoi_200k(self):
        assert normalize_budget_text("dưới 200k") == 200000

    def test_toi_da_35k(self):
        assert normalize_budget_text("tối đa 35k") == 35000

    def test_max_40k(self):
        assert normalize_budget_text("max 40k") == 40000

    def test_in_sentence_200000(self):
        """'ngân sách 200000' → 200000"""
        result = normalize_budget_text("ngân sách 200000 đồng")
        assert result == 200000

    def test_in_sentence_200_nghìn(self):
        result = normalize_budget_text("khoảng 200 nghìn thôi")
        assert result == 200000

    def test_in_sentence_1_trieu(self):
        result = normalize_budget_text("ăn khoảng 1 triệu được")
        assert result == 1000000

    def test_200_dot_000_in_sentence(self):
        result = normalize_budget_text("ăn dưới 200.000đ")
        assert result == 200000

    def test_no_budget_in_text(self):
        """Câu không có ngân sách → None"""
        result = normalize_budget_text("Hôm nay trời đẹp quá!")
        assert result is None

    def test_q5_no_budget(self):
        result = normalize_budget_text("tìm quán ở quận 5")
        assert result is None

    def test_budget_with_vnd_suffix(self):
        result = normalize_budget_text("khoảng 200,000 VND")
        assert result == 200000
