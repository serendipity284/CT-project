"""
HEANA - Hard Constraint Filter + Personalized Soft Ranking
Compliant with Problem Specification sections 1.4 & PAT-01 / PAT-02
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, time, date
from typing import Any, Optional


# ------------------------------------------------------------
# Data structures
# ------------------------------------------------------------

@dataclass
class UserPreference:
    w_price: float = 0.30
    w_distance: float = 0.30
    w_quality: float = 0.30
    w_freshness: float = 0.10
    allergies: list[str] = field(default_factory=list)

    def normalized_weights(self) -> tuple[float, float, float, float]:
        total = self.w_price + self.w_distance + self.w_quality + self.w_freshness
        if total <= 0:
            return 0.25, 0.25, 0.25, 0.25
        return (
            self.w_price / total,
            self.w_distance / total,
            self.w_quality / total,
            self.w_freshness / total,
        )


@dataclass
class DishCandidate:
    dish_id: int
    dish_name: str
    price: int
    ingredients: list[str]
    place_id: int


@dataclass
class PlaceCandidate:
    place_id: int
    name: str
    campus: str
    address: str
    lat: float
    lng: float
    alley_entrance_lat: Optional[float]
    alley_entrance_lng: Optional[float]
    open_time: Optional[time]
    close_time: Optional[time]
    hours_text: str
    price_min: int
    price_max: int
    cuisine: str
    rating_avg: float
    rating_count: int
    updated_at: datetime
    image_url: Optional[str]
    matched_dishes: list[DishCandidate] = field(default_factory=list)
    # Computed
    distance_m: float = 0.0
    score: float = 0.0
    s_feedback: float = 0.0
    s_price: float = 0.0
    s_distance: float = 0.0
    s_freshness: float = 0.0


# ------------------------------------------------------------
# Utility functions
# ------------------------------------------------------------

def haversine(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Khoảng cách đường chim bay (mét)."""
    R = 6371000.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * R * math.asin(min(1.0, math.sqrt(a)))


def normalize_ingredient(s: str) -> str:
    """Chuẩn hóa tên thành phần để so khớp dị ứng."""
    return s.strip().lower()


def has_allergy_conflict(ingredients: list[str], allergies: list[str]) -> bool:
    """
    Hard Filter - Allergy Rule (Spec 1.4 & PAT-01)
    Trả về True nếu có giao giữa ingredients và allergies (bị cấm).
    """
    if not allergies:
        return False
    ing_set = {normalize_ingredient(x) for x in ingredients}
    all_set = {normalize_ingredient(x) for x in allergies}
    return len(ing_set & all_set) > 0


def is_open_now(
    open_time: Optional[time],
    close_time: Optional[time],
    now: Optional[datetime] = None,
) -> bool:
    """
    Hard Filter - Opening Hours Rule (Spec 1.4)
    Hỗ trợ trường hợp qua đêm (close < open).
    """
    if open_time is None or close_time is None:
        return True  # Không có thông tin → cho qua (có thể thay bằng False tùy chính sách)

    now = now or datetime.now()
    current = now.time()

    if open_time <= close_time:
        # Trong ngày: 06:00 - 14:00
        return open_time <= current <= close_time
    else:
        # Qua đêm: 18:00 - 02:00
        return current >= open_time or current <= close_time


def bayesian_rating(avg: float, count: int, prior_avg: float = 3.5, prior_count: int = 10) -> float:
    """
    Bayesian average để tránh quán ít review bị đánh giá quá cao/thấp.
    Chuẩn hóa về [0, 1] sau này.
    """
    if count + prior_count == 0:
        return prior_avg
    return (prior_avg * prior_count + avg * count) / (prior_count + count)


def linear_freshness(updated_at: datetime, max_days: int = 120) -> float:
    """
    S_freshness: Linear decay trong 120 ngày (Spec 1.4).
    Trả về giá trị [0, 1].
    """
    if updated_at.tzinfo is not None:
        updated_at = updated_at.replace(tzinfo=None)
    days = (datetime.now() - updated_at).days
    if days <= 0:
        return 1.0
    return max(0.0, 1.0 - days / max_days)


# ------------------------------------------------------------
# Core Pipeline
# ------------------------------------------------------------

def hard_filter(
    candidates: list[PlaceCandidate],
    allergies: list[str],
    required_dish: Optional[str] = None,
    max_price: Optional[int] = None,
    now: Optional[datetime] = None,
) -> list[PlaceCandidate]:
    """
    Hard Constraint Filter (Spec 1.4 + PAT-01)
    Thứ tự:
      1. Lọc dị ứng (loại bỏ món/quán có ingredients giao với allergies)
      2. Lọc giờ mở cửa
      3. Lọc món + giá (nếu có required_dish / max_price)
    """
    result: list[PlaceCandidate] = []
    req = (required_dish or "").strip().lower()

    for place in candidates:
        # 2. Opening hours
        if not is_open_now(place.open_time, place.close_time, now):
            continue

        # 1 + 3. Allergy + Dish match
        valid_dishes: list[DishCandidate] = []
        for dish in place.matched_dishes:
            # Allergy hard rule
            if has_allergy_conflict(dish.ingredients, allergies):
                continue
            # Dish name match (nếu user yêu cầu món cụ thể)
            if req and req not in dish.dish_name.lower() and req not in place.cuisine.lower():
                continue
            # Price constraint
            if max_price is not None and dish.price > max_price:
                continue
            valid_dishes.append(dish)

        # Nếu user yêu cầu món cụ thể mà không còn món hợp lệ → loại quán
        if req and not valid_dishes:
            continue

        # Nếu không yêu cầu món cụ thể, vẫn giữ quán nếu còn ít nhất 1 món không dị ứng
        # (hoặc không có menu chi tiết)
        if not place.matched_dishes:
            # Không có dữ liệu món → chỉ check allergy ở level quán (nếu sau này có)
            place.matched_dishes = []
            result.append(place)
        elif valid_dishes:
            place.matched_dishes = valid_dishes
            # Cập nhật price_min/max theo món còn lại
            prices = [d.price for d in valid_dishes]
            place.price_min = min(prices)
            place.price_max = max(prices)
            result.append(place)

    return result


def compute_soft_scores(
    places: list[PlaceCandidate],
    preference: UserPreference,
    user_lat: float,
    user_lng: float,
    max_radius_m: float = 2000.0,
) -> list[PlaceCandidate]:
    """
    Personalized Soft Ranking (Spec 1.4 + PAT-02)
    S = w1*S_feedback + w2*S_price + w3*S_distance + w4*S_freshness
    Tất cả thành phần được chuẩn hóa về [0, 1].
    """
    if not places:
        return []

    w_price, w_dist, w_qual, w_fresh = preference.normalized_weights()

    # Pre-compute min/max for price & distance (min-max normalization)
    prices = []
    distances = []
    for p in places:
        # Dùng giá trung bình của các món khớp, hoặc price_min
        if p.matched_dishes:
            avg_price = sum(d.price for d in p.matched_dishes) / len(p.matched_dishes)
        else:
            avg_price = (p.price_min + p.price_max) / 2
        prices.append(avg_price)

        # Ưu tiên khoảng cách đến cổng hẻm nếu có
        tlat = p.alley_entrance_lat if p.alley_entrance_lat is not None else p.lat
        tlng = p.alley_entrance_lng if p.alley_entrance_lng is not None else p.lng
        dist = haversine(user_lat, user_lng, tlat, tlng)
        p.distance_m = dist
        distances.append(dist)

    min_price, max_price = min(prices), max(prices)
    price_range = max(max_price - min_price, 1.0)

    min_dist, max_dist = min(distances), max(distances)
    # Dùng max_radius_m làm trần để quán ngoài bán kính bị điểm thấp
    dist_range = max(max(max_dist, max_radius_m) - min_dist, 1.0)

    for i, p in enumerate(places):
        # S_feedback (Bayesian → [0,1])
        bayes = bayesian_rating(p.rating_avg, p.rating_count)
        p.s_feedback = max(0.0, min(1.0, (bayes - 1.0) / 4.0))  # rating 1-5 → 0-1

        # S_price (càng rẻ càng cao)
        p.s_price = 1.0 - (prices[i] - min_price) / price_range

        # S_distance (càng gần càng cao)
        p.s_distance = 1.0 - (p.distance_m - min_dist) / dist_range
        # Phạt thêm nếu vượt bán kính mong muốn
        if p.distance_m > max_radius_m:
            p.s_distance *= 0.3

        # S_freshness
        p.s_freshness = linear_freshness(p.updated_at)

        # Final score
        p.score = (
            w_qual * p.s_feedback
            + w_price * p.s_price
            + w_dist * p.s_distance
            + w_fresh * p.s_freshness
        )

    # Sort giảm dần theo score
    places.sort(key=lambda x: x.score, reverse=True)
    return places


def rank_places(
    candidates: list[PlaceCandidate],
    preference: UserPreference,
    user_lat: float,
    user_lng: float,
    required_dish: Optional[str] = None,
    max_price: Optional[int] = None,
    max_radius_m: float = 2000.0,
    top_k: int = 15,
    now: Optional[datetime] = None,
) -> list[PlaceCandidate]:
    """
    Full pipeline: Hard Filter → Soft Ranking → Top-K
    """
    filtered = hard_filter(
        candidates=candidates,
        allergies=preference.allergies,
        required_dish=required_dish,
        max_price=max_price,
        now=now,
    )
    scored = compute_soft_scores(
        places=filtered,
        preference=preference,
        user_lat=user_lat,
        user_lng=user_lng,
        max_radius_m=max_radius_m,
    )
    return scored[:top_k]


# ------------------------------------------------------------
# Constraint Relaxation (PAT-03)
# ------------------------------------------------------------

def suggest_relaxation(
    original_count: int,
    required_dish: Optional[str],
    max_price: Optional[int],
    allergies: list[str],
) -> dict[str, Any]:
    """
    Khi kết quả rỗng, gợi ý nới lỏng điều kiện (Spec 1.5 - Giai đoạn 2C).
    """
    suggestions = []
    if required_dish:
        suggestions.append({
            "type": "remove_dish",
            "message": f"Thử bỏ yêu cầu món «{required_dish}» để xem thêm quán khác.",
        })
    if max_price is not None and max_price < 80000:
        suggestions.append({
            "type": "increase_budget",
            "message": f"Thử tăng ngân sách lên {max_price + 15000:,}đ trở lên.",
            "new_budget": max_price + 15000,
        })
    if allergies:
        suggestions.append({
            "type": "review_allergies",
            "message": "Một số quán bị loại do chứa thành phần dị ứng. Bạn có muốn xem lại danh sách dị ứng không?",
        })
    suggestions.append({
        "type": "increase_radius",
        "message": "Thử mở rộng bán kính tìm kiếm thêm 500m–1km.",
    })
    return {
        "has_results": original_count > 0,
        "suggestions": suggestions,
    }