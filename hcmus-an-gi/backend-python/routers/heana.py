"""
HEANA API Router - Các endpoint chính theo Spec
Tích hợp vào app FastAPI hiện có bằng: app.include_router(heana.router, prefix="/api")
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Header
from jose import JWTError, jwt

from models.schemas import (
    ChatRequest,
    ChatResponse,
    DirectionsRequest,
    DirectionsResponse,
    OnboardingSurvey,
    PreferenceOut,
    PreferenceUpdate,
    RouteStepOut,
    SearchRequest,
    SearchResponse,
    ExtractedIntent,
)
from services.ranking import UserPreference
from services.search_service import (
    candidate_to_dict,
    preference_from_survey,
    run_search,
)
from services.alley_routing import (
    AlleyGraph,
    build_alley_route,
    load_graph_from_rows,
)

router = APIRouter(tags=["HEANA"])

# ------------------------------------------------------------
# Giả lập DB access (thay bằng mysql.connector thật trong production)
# ------------------------------------------------------------

# Trong code thật, bạn sẽ inject connection hoặc dùng dependency.
# Ở đây để demo logic, ta giả định có các hàm fetch_*.

def get_db_connection():
    """Placeholder - thay bằng connection pool thật."""
    import mysql.connector
    return mysql.connector.connect(
        host=os.getenv("MYSQL_HOST", "127.0.0.1"),
        port=int(os.getenv("MYSQL_PORT", "3306")),
        user=os.getenv("MYSQL_USER", "root"),
        password=os.getenv("MYSQL_PASSWORD", ""),
        database=os.getenv("MYSQL_DATABASE", "hcmus_an_gi"),
    )


def fetch_places(campus: Optional[str] = None) -> list[dict]:
    conn = get_db_connection()
    cur = conn.cursor(dictionary=True)
    if campus:
        cur.execute("SELECT * FROM places WHERE is_active=1 AND campus=%s", (campus,))
    else:
        cur.execute("SELECT * FROM places WHERE is_active=1")
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows


def fetch_dishes(place_ids: list[int]) -> list[dict]:
    if not place_ids:
        return []
    conn = get_db_connection()
    cur = conn.cursor(dictionary=True)
    placeholders = ",".join(["%s"] * len(place_ids))
    cur.execute(
        f"SELECT id, place_id, name, price, ingredients FROM place_dishes "
        f"WHERE place_id IN ({placeholders}) AND is_available=1 AND price IS NOT NULL",
        place_ids,
    )
    rows = cur.fetchall()
    cur.close()
    conn.close()
    # Parse JSON ingredients
    for r in rows:
        if isinstance(r.get("ingredients"), str):
            try:
                r["ingredients"] = json.loads(r["ingredients"])
            except Exception:
                r["ingredients"] = []
    return rows


def fetch_user_preference(user_id: str) -> UserPreference:
    conn = get_db_connection()
    cur = conn.cursor(dictionary=True)
    cur.execute("SELECT * FROM user_preferences WHERE user_id=%s", (user_id,))
    row = cur.fetchone()
    cur.close()
    conn.close()
    if not row:
        return UserPreference()
    allergies = row.get("allergies") or []
    if isinstance(allergies, str):
        try:
            allergies = json.loads(allergies)
        except Exception:
            allergies = []
    return UserPreference(
        w_price=float(row["w_price"]),
        w_distance=float(row["w_distance"]),
        w_quality=float(row["w_quality"]),
        w_freshness=float(row["w_freshness"]),
        allergies=list(allergies),
    )


def save_user_preference(user_id: str, pref: UserPreference, survey_done: bool = True):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO user_preferences (user_id, w_price, w_distance, w_quality, w_freshness, allergies, survey_done)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE
          w_price=VALUES(w_price),
          w_distance=VALUES(w_distance),
          w_quality=VALUES(w_quality),
          w_freshness=VALUES(w_freshness),
          allergies=VALUES(allergies),
          survey_done=VALUES(survey_done)
        """,
        (
            user_id,
            pref.w_price,
            pref.w_distance,
            pref.w_quality,
            pref.w_freshness,
            json.dumps(pref.allergies, ensure_ascii=False),
            1 if survey_done else 0,
        ),
    )
    conn.commit()
    cur.close()
    conn.close()


def fetch_alley_graph_for_place(place_id: int) -> AlleyGraph:
    conn = get_db_connection()
    cur = conn.cursor(dictionary=True)
    # Lấy tất cả node liên quan (đơn giản: theo campus của quán)
    cur.execute("SELECT campus FROM places WHERE id=%s", (place_id,))
    prow = cur.fetchone()
    campus = prow["campus"] if prow else None

    if campus:
        cur.execute("SELECT * FROM alley_nodes WHERE campus=%s OR place_id=%s", (campus, place_id))
    else:
        cur.execute("SELECT * FROM alley_nodes WHERE place_id=%s", (place_id,))
    nodes = cur.fetchall()

    node_ids = [n["id"] for n in nodes]
    edges = []
    if node_ids:
        ph = ",".join(["%s"] * len(node_ids))
        cur.execute(
            f"SELECT * FROM alley_edges WHERE from_node_id IN ({ph}) OR to_node_id IN ({ph})",
            node_ids + node_ids,
        )
        edges = cur.fetchall()
    cur.close()
    conn.close()
    return load_graph_from_rows(nodes, edges)


# Auth helper (giả định dùng JWT giống app.py hiện tại)
JWT_SECRET = os.getenv("JWT_SECRET", "dev-secret-change-me")


def get_current_user_id(authorization: Optional[str] = Header(None)) -> Optional[str]:
    if not authorization or not authorization.startswith("Bearer "):
        return None
    token = authorization.split(" ", 1)[1]
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
        return payload.get("sub")
    except JWTError:
        return None


# ------------------------------------------------------------
# Endpoints
# ------------------------------------------------------------

@router.post("/onboarding", response_model=PreferenceOut)
def submit_onboarding(
    body: OnboardingSurvey,
    user_id: Optional[str] = Depends(get_current_user_id),
):
    """Spec 1.1 - Khảo sát sở thích ngay sau khi tạo tài khoản."""
    if not user_id:
        raise HTTPException(401, "Cần đăng nhập để lưu preference.")
    pref = preference_from_survey(
        price_importance=body.price_importance,
        distance_importance=body.distance_importance,
        quality_importance=body.quality_importance,
        allergies_text=body.allergies_text,
    )
    save_user_preference(user_id, pref, survey_done=True)
    return PreferenceOut(
        w_price=pref.w_price,
        w_distance=pref.w_distance,
        w_quality=pref.w_quality,
        w_freshness=pref.w_freshness,
        allergies=pref.allergies,
        survey_done=True,
    )


@router.get("/preferences", response_model=PreferenceOut)
def get_preferences(user_id: Optional[str] = Depends(get_current_user_id)):
    if not user_id:
        raise HTTPException(401, "Cần đăng nhập.")
    pref = fetch_user_preference(user_id)
    return PreferenceOut(
        w_price=pref.w_price,
        w_distance=pref.w_distance,
        w_quality=pref.w_quality,
        w_freshness=pref.w_freshness,
        allergies=pref.allergies,
        survey_done=True,
    )


@router.put("/preferences", response_model=PreferenceOut)
def update_preferences(
    body: PreferenceUpdate,
    user_id: Optional[str] = Depends(get_current_user_id),
):
    if not user_id:
        raise HTTPException(401, "Cần đăng nhập.")
    pref = UserPreference(
        w_price=body.w_price,
        w_distance=body.w_distance,
        w_quality=body.w_quality,
        w_freshness=body.w_freshness,
        allergies=body.allergies,
    )
    save_user_preference(user_id, pref, survey_done=True)
    return PreferenceOut(
        w_price=pref.w_price,
        w_distance=pref.w_distance,
        w_quality=pref.w_quality,
        w_freshness=pref.w_freshness,
        allergies=pref.allergies,
        survey_done=True,
    )


@router.post("/search", response_model=SearchResponse)
def search_places(
    body: SearchRequest,
    user_id: Optional[str] = Depends(get_current_user_id),
):
    """
    Full search pipeline:
    Hard Filter (Allergy + Hours + Dish) → Soft Ranking → Top 15
    """
    # Preference
    if user_id:
        pref = fetch_user_preference(user_id)
        # Merge allergies từ request (nếu user muốn override tạm)
        if body.allergies:
            pref.allergies = list(set(pref.allergies + body.allergies))
    else:
        pref = UserPreference(allergies=body.allergies)

    place_rows = fetch_places(body.campus)
    place_ids = [p["id"] for p in place_rows]
    dish_rows = fetch_dishes(place_ids)

    ranked, relaxation = run_search(
        place_rows=place_rows,
        dish_rows=dish_rows,
        preference=pref,
        user_lat=body.user_lat,
        user_lng=body.user_lng,
        required_dish=body.required_dish,
        max_price=body.budget,
        max_radius_m=float(body.radius_m),
        top_k=15,
    )

    return SearchResponse(
        places=[candidate_to_dict(p) for p in ranked],  # type: ignore
        total=len(ranked),
        relaxation=relaxation if not ranked else None,
    )


@router.post("/directions", response_model=DirectionsResponse)
def get_directions(body: DirectionsRequest):
    """
    Dẫn đường 2 chặng:
    - Stage 1: GPS → Alley Entrance (OSRM - gọi external)
    - Stage 2: Landmark steps trong hẻm (Dijkstra trên alley_graph)
    """
    # Lấy thông tin quán
    places = fetch_places()
    place = next((p for p in places if p["id"] == body.place_id), None)
    if not place:
        raise HTTPException(404, "Không tìm thấy quán.")

    # Stage 2: Alley graph
    graph = fetch_alley_graph_for_place(body.place_id)
    alley_result = build_alley_route(graph, body.place_id)

    stage2_steps = []
    stage2_total = 0.0
    has_alley = alley_result.found
    if has_alley:
        stage2_total = alley_result.total_distance_m
        stage2_steps = [
            RouteStepOut(
                node_id=s.node_id,
                node_name=s.node_name,
                instruction=s.instruction,
                distance_m=s.distance_m,
                lat=s.lat,
                lng=s.lng,
                image_url=s.image_url,
                node_type=s.node_type,
            )
            for s in alley_result.steps
        ]

    # Stage 1: đến cổng hẻm (hoặc đến quán nếu không có alley data)
    target_lat = place.get("alley_entrance_lat") or place["lat"]
    target_lng = place.get("alley_entrance_lng") or place["lng"]
    if has_alley and alley_result.entrance_node:
        target_lat = alley_result.entrance_node.lat
        target_lng = alley_result.entrance_node.lng

    # Gọi OSRM (public)
    import urllib.request
    import urllib.parse
    stage1_poly = []
    stage1_dist = 0.0
    stage1_dur = 0.0
    try:
        url = (
            f"https://router.project-osrm.org/route/v1/walking/"
            f"{body.user_lng},{body.user_lat};{target_lng},{target_lat}"
            f"?overview=full&geometries=geojson"
        )
        req = urllib.request.Request(url, headers={"User-Agent": "heana/1.0"})
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read().decode())
        route = data.get("routes", [None])[0]
        if route:
            stage1_poly = route["geometry"]["coordinates"]
            stage1_dist = route["distance"]
            stage1_dur = route["duration"]
    except Exception:
        pass

    msg = ""
    if not has_alley:
        msg = "Quán chưa có dữ liệu dẫn đường trong hẻm. Chỉ hiển thị đường đến vị trí quán."
    elif not stage1_poly:
        msg = "Không lấy được đường GPS. Vẫn có hướng dẫn từng bước trong hẻm."

    return DirectionsResponse(
        place_id=body.place_id,
        place_name=place["name"],
        stage1_distance_m=round(stage1_dist),
        stage1_duration_sec=round(stage1_dur),
        stage1_polyline=stage1_poly,
        stage2=stage2_steps,
        stage2_total_m=round(stage2_total),
        has_alley_data=has_alley,
        message=msg,
    )