"""
config.py – Cấu hình tập trung cho Input Understanding.

Tất cả giá trị mặc định và ngưỡng giới hạn được định nghĩa tại đây,
không hardcode rải rác trong mã nguồn.
"""

# Ngưỡng giá trị hợp lệ
MIN_BUDGET: int = 5_000            # 5.000 VND
MAX_BUDGET: int = 2_000_000        # 2.000.000 VND

MIN_RADIUS_M: int = 100            # 100 mét
MAX_RADIUS_M: int = 10_000         # 10.000 mét (10 km)

# Giới hạn thời gian sống (TTL) của ngữ cảnh cảm xúc
EMOTION_TTL_TURNS: int = 5

# Ngưỡng tin cậy tối thiểu cho cảm xúc
EMOTION_MIN_CONFIDENCE: float = 0.5
