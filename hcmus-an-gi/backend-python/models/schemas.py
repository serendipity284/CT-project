"""
HEANA Pydantic Schemas - Input / Output / Preference
"""

from __future__ import annotations

from datetime import datetime, time
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field, field_validator


# ------------------------------------------------------------
# User Preference / Onboarding
# ------------------------------------------------------------

class PreferenceUpdate(BaseModel):
    w_price: float = Field(0.30, ge=0.0, le=1.0)
    w_distance: float = Field(0.30, ge=0.0, le=1.0)
    w_quality: float = Field(0.30, ge=0.0, le=1.0)
    w_freshness: float = Field(0.10, ge=0.0, le=1.0)
    allergies: list[str] = Field(default_factory=list)

    @field_validator("allergies", mode="before")
    @classmethod
    def clean_allergies(cls, v):
        if v is None:
            return []
        return [str(x).strip().lower() for x in v if str(x).strip()]


class PreferenceOut(PreferenceUpdate):
    survey_done: bool = False
    updated_at: Optional[datetime] = None


class OnboardingSurvey(BaseModel):
    """4 câu hỏi onboarding theo Spec 1.1"""
    price_importance: int = Field(..., ge=1, le=5, description="1=không quan tâm, 5=rất quan tâm giá")
    distance_importance: int = Field(..., ge=1, le=5)
    quality_importance: int = Field(..., ge=1, le=5)
    allergies_text: str = Field("", description="Các thành phần dị ứng, cách nhau bởi dấu phẩy")


# ------------------------------------------------------------
# Input Understanding (mở rộng)
# ------------------------------------------------------------

class ExtractedIntent(BaseModel):
    intent: Literal[
        "search_food",
        "refine_search",
        "recommendation",
        "ask_directions",
        "other",
    ] = "search_food"

    campus: Optional[Literal["q5", "lang"]] = None
    budget: Optional[int] = Field(None, description="max_price VND")
    radius_m: Optional[int] = None
    required_dish: Optional[str] = None
    cuisine: Optional[str] = None
    keywords: list[str] = Field(default_factory=list)
    # Có thể trích xuất dị ứng nếu user nhắc trong câu
    mentioned_allergies: list[str] = Field(default_factory=list)


class ChatRequest(BaseModel):
    message: str
    previous: dict[str, Any] = Field(default_factory=dict)
    user_lat: Optional[float] = None
    user_lng: Optional[float] = None


class ChatResponse(BaseModel):
    intent: ExtractedIntent
    reply: str
    ready: bool = False
    missing_fields: list[str] = Field(default_factory=list)
    places: list[dict] = Field(default_factory=list)
    relaxation: Optional[dict] = None


# ------------------------------------------------------------
# Search / Rank
# ------------------------------------------------------------

class SearchRequest(BaseModel):
    campus: Optional[Literal["q5", "lang"]] = None
    budget: Optional[int] = None
    radius_m: int = 1000
    required_dish: Optional[str] = None
    user_lat: float
    user_lng: float
    # Nếu đã login, backend sẽ lấy preference từ DB
    # Có thể override tạm:
    allergies: list[str] = Field(default_factory=list)


class DishOut(BaseModel):
    dish_id: int
    dish_name: str
    price: int
    ingredients: list[str] = Field(default_factory=list)


class PlaceOut(BaseModel):
    place_id: int
    name: str
    campus: str
    address: str
    lat: float
    lng: float
    alley_entrance_lat: Optional[float] = None
    alley_entrance_lng: Optional[float] = None
    hours_text: str = ""
    price_min: int
    price_max: int
    cuisine: str
    rating_avg: float
    rating_count: int
    distance_m: float
    score: float
    matched_dishes: list[DishOut] = Field(default_factory=list)
    image_url: Optional[str] = None
    # Breakdown (debug / explainability)
    s_feedback: float = 0.0
    s_price: float = 0.0
    s_distance: float = 0.0
    s_freshness: float = 0.0


class SearchResponse(BaseModel):
    places: list[PlaceOut]
    total: int
    relaxation: Optional[dict] = None


# ------------------------------------------------------------
# Directions 2-stage
# ------------------------------------------------------------

class DirectionsRequest(BaseModel):
    place_id: int
    user_lat: float
    user_lng: float


class RouteStepOut(BaseModel):
    node_id: int
    node_name: str
    instruction: str
    distance_m: float
    lat: float
    lng: float
    image_url: Optional[str] = None
    node_type: str


class DirectionsResponse(BaseModel):
    place_id: int
    place_name: str
    # Chặng 1: GPS → Entrance (polyline từ OSRM hoặc tương đương)
    stage1_distance_m: float = 0.0
    stage1_duration_sec: float = 0.0
    stage1_polyline: list[list[float]] = Field(default_factory=list)  # [[lng,lat], ...]
    # Chặng 2: Landmark steps trong hẻm
    stage2: list[RouteStepOut] = Field(default_factory=list)
    stage2_total_m: float = 0.0
    has_alley_data: bool = False
    message: str = ""