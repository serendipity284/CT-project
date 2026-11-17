"""
HEANA Search Service - Orchestrates Hard Filter + Soft Ranking + Preference
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from services.ranking import (
    DishCandidate,
    PlaceCandidate,
    UserPreference,
    rank_places,
    suggest_relaxation,
)


def rows_to_candidates(
    place_rows: list[dict],
    dish_rows: list[dict],
) -> list[PlaceCandidate]:
    """
    Chuyển kết quả query DB thành list PlaceCandidate.
    place_rows: kết quả SELECT từ bảng places
    dish_rows: kết quả SELECT từ bảng dishes (có thể join hoặc query riêng)
    """
    dishes_by_place: dict[int, list[DishCandidate]] = {}
    for d in dish_rows:
        pid = d["place_id"]
        ingredients = d.get("ingredients") or []
        if isinstance(ingredients, str):
            import json
            try:
                ingredients = json.loads(ingredients)
            except Exception:
                ingredients = []
        dishes_by_place.setdefault(pid, []).append(
            DishCandidate(
                dish_id=d["id"],
                dish_name=d["name"],
                price=int(d["price"]),
                ingredients=list(ingredients),
                place_id=pid,
            )
        )

    candidates: list[PlaceCandidate] = []
    for p in place_rows:
        open_t = p.get("open_time")
        close_t = p.get("close_time")
        # mysql.connector có thể trả timedelta hoặc time
        if open_t is not None and not hasattr(open_t, "hour"):
            open_t = None
        if close_t is not None and not hasattr(close_t, "hour"):
            close_t = None

        updated = p.get("updated_at") or datetime.now()
        if isinstance(updated, str):
            try:
                updated = datetime.fromisoformat(updated.replace("Z", "+00:00")).replace(tzinfo=None)
            except Exception:
                updated = datetime.now()

        candidates.append(
            PlaceCandidate(
                place_id=p["id"],
                name=p["name"],
                campus=p["campus"],
                address=p["address"],
                lat=float(p["lat"]),
                lng=float(p["lng"]),
                alley_entrance_lat=float(p["alley_entrance_lat"]) if p.get("alley_entrance_lat") else None,
                alley_entrance_lng=float(p["alley_entrance_lng"]) if p.get("alley_entrance_lng") else None,
                open_time=open_t,
                close_time=close_t,
                hours_text=p.get("hours_text") or "",
                price_min=int(p.get("price_min") or 0),
                price_max=int(p.get("price_max") or 0),
                cuisine=p.get("cuisine") or "",
                rating_avg=float(p.get("rating_avg") or 0),
                rating_count=int(p.get("rating_count") or 0),
                updated_at=updated,
                image_url=p.get("image_url"),
                matched_dishes=dishes_by_place.get(p["id"], []),
            )
        )
    return candidates


def run_search(
    place_rows: list[dict],
    dish_rows: list[dict],
    preference: UserPreference,
    user_lat: float,
    user_lng: float,
    required_dish: Optional[str] = None,
    max_price: Optional[int] = None,
    max_radius_m: float = 2000.0,
    top_k: int = 15,
) -> tuple[list[PlaceCandidate], dict]:
    """
    Chạy full pipeline và trả về (danh sách đã rank, relaxation info).
    """
    candidates = rows_to_candidates(place_rows, dish_rows)

    ranked = rank_places(
        candidates=candidates,
        preference=preference,
        user_lat=user_lat,
        user_lng=user_lng,
        required_dish=required_dish,
        max_price=max_price,
        max_radius_m=max_radius_m,
        top_k=top_k,
    )

    relaxation = None
    if not ranked:
        relaxation = suggest_relaxation(
            original_count=0,
            required_dish=required_dish,
            max_price=max_price,
            allergies=preference.allergies,
        )

    return ranked, relaxation or {}


def preference_from_survey(
    price_importance: int,
    distance_importance: int,
    quality_importance: int,
    allergies_text: str,
) -> UserPreference:
    """
    Chuyển kết quả 4 câu onboarding (thang 1-5) thành trọng số.
    """
    # Chuẩn hóa importance 1-5 → trọng số
    total = price_importance + distance_importance + quality_importance
    if total == 0:
        total = 3
    # freshness mặc định thấp hơn
    w_price = price_importance / (total + 1.5)
    w_distance = distance_importance / (total + 1.5)
    w_quality = quality_importance / (total + 1.5)
    w_freshness = 1.5 / (total + 1.5)

    allergies = [
        a.strip().lower()
        for a in allergies_text.replace(";", ",").split(",")
        if a.strip()
    ]

    return UserPreference(
        w_price=round(w_price, 3),
        w_distance=round(w_distance, 3),
        w_quality=round(w_quality, 3),
        w_freshness=round(w_freshness, 3),
        allergies=allergies,
    )


def candidate_to_dict(p: PlaceCandidate) -> dict[str, Any]:
    """Serialize để trả API."""
    return {
        "place_id": p.place_id,
        "name": p.name,
        "campus": p.campus,
        "address": p.address,
        "lat": p.lat,
        "lng": p.lng,
        "alley_entrance_lat": p.alley_entrance_lat,
        "alley_entrance_lng": p.alley_entrance_lng,
        "hours_text": p.hours_text,
        "price_min": p.price_min,
        "price_max": p.price_max,
        "cuisine": p.cuisine,
        "rating_avg": p.rating_avg,
        "rating_count": p.rating_count,
        "distance_m": round(p.distance_m),
        "score": round(p.score, 4),
        "matched_dishes": [
            {
                "dish_id": d.dish_id,
                "dish_name": d.dish_name,
                "price": d.price,
                "ingredients": d.ingredients,
            }
            for d in p.matched_dishes
        ],
        "image_url": p.image_url,
        "s_feedback": round(p.s_feedback, 3),
        "s_price": round(p.s_price, 3),
        "s_distance": round(p.s_distance, 3),
        "s_freshness": round(p.s_freshness, 3),
    }