"""
HEANA - API đóng góp dữ liệu hẻm (crowdsourcing).

Gắn vào app.py:
    from routers.alley import router as alley_router
    app.include_router(alley_router, prefix="/api/heana")
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, model_validator

from routers.heana import get_current_user_id, get_db_connection
from services.alley_contrib import plan_chain

router = APIRouter(tags=["HEANA-Alley"])

VN_LAT = dict(ge=8, le=24)
VN_LNG = dict(ge=102, le=110)


class EntranceIn(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    lat: float = Field(**VN_LAT)
    lng: float = Field(**VN_LNG)
    description: Optional[str] = Field(default=None, max_length=255)


class StepIn(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    instruction: str = Field(min_length=4, max_length=300)
    distance_m: Optional[float] = Field(default=None, gt=0, le=1000)
    lat: Optional[float] = Field(default=None, **VN_LAT)
    lng: Optional[float] = Field(default=None, **VN_LNG)
    description: Optional[str] = Field(default=None, max_length=255)
    image_url: Optional[str] = Field(default=None, max_length=500)


class AlleyRouteIn(BaseModel):
    place_id: int
    entrance_node_id: Optional[int] = None  # chọn cổng đã có...
    entrance: Optional[EntranceIn] = None   # ...hoặc tạo cổng mới
    steps: list[StepIn] = Field(default_factory=list, max_length=12)
    final_instruction: str = Field(min_length=4, max_length=300)
    final_distance_m: Optional[float] = Field(default=None, gt=0, le=1000)

    @model_validator(mode="after")
    def exactly_one_entrance(self):
        if (self.entrance_node_id is None) == (self.entrance is None):
            raise ValueError("Cần chọn đúng một: entrance_node_id hoặc entrance mới.")
        return self


@router.get("/alley/entrances")
def list_entrances(campus: Optional[str] = None):
    """Danh sách cổng hẻm đã có (để người đóng góp chọn lại thay vì tạo trùng)."""
    if campus not in (None, "q5", "lang"):
        raise HTTPException(400, "campus phải là q5 hoặc lang")
    conn = get_db_connection()
    cur = conn.cursor(dictionary=True)
    try:
        sql = "SELECT id, name, lat, lng, campus, description FROM alley_nodes WHERE node_type='entrance'"
        params: list = []
        if campus:
            sql += " AND campus=%s"
            params.append(campus)
        cur.execute(sql + " ORDER BY id", params)
        return [
            {**r, "lat": float(r["lat"]), "lng": float(r["lng"])}
            for r in cur.fetchall()
        ]
    finally:
        cur.close()
        conn.close()


@router.post("/alley/route")
def contribute_route(body: AlleyRouteIn, user_id: Optional[str] = Depends(get_current_user_id)):
    """
    Thêm trọn một tuyến: cổng hẻm → các điểm mốc → quán (trong 1 transaction).
    Mỗi quán hiện chỉ nhận 1 tuyến; quán đã có dữ liệu hẻm trả 409.
    """
    if not user_id:
        raise HTTPException(401, "Cần đăng nhập để đóng góp.")

    conn = get_db_connection()
    cur = conn.cursor(dictionary=True)
    try:
        cur.execute(
            "SELECT id, campus, lat, lng FROM places WHERE id=%s AND is_active=1",
            (body.place_id,),
        )
        place = cur.fetchone()
        if not place:
            raise HTTPException(404, "Không tìm thấy quán.")
        campus = place["campus"]

        # --- quán đã có node eatery / cạnh chưa? ---
        cur.execute(
            "SELECT id FROM alley_nodes WHERE place_id=%s AND node_type='eatery' LIMIT 1",
            (body.place_id,),
        )
        eatery_row = cur.fetchone()
        if eatery_row:
            cur.execute(
                "SELECT 1 FROM alley_edges WHERE from_node_id=%s OR to_node_id=%s LIMIT 1",
                (eatery_row["id"], eatery_row["id"]),
            )
            if cur.fetchone():
                raise HTTPException(409, "Quán này đã có dữ liệu đường đi trong hẻm.")

        # --- cổng hẻm ---
        if body.entrance_node_id is not None:
            cur.execute(
                "SELECT id, lat, lng FROM alley_nodes WHERE id=%s AND node_type='entrance'",
                (body.entrance_node_id,),
            )
            ent = cur.fetchone()
            if not ent:
                raise HTTPException(404, "Không tìm thấy cổng hẻm đã chọn.")
            entrance_id = ent["id"]
            ent_pos = (float(ent["lat"]), float(ent["lng"]))
        else:
            e = body.entrance
            assert e is not None
            cur.execute(
                "INSERT INTO alley_nodes (place_id, name, lat, lng, node_type, description, campus) "
                "VALUES (NULL, %s, %s, %s, 'entrance', %s, %s)",
                (e.name.strip(), e.lat, e.lng, e.description, campus),
            )
            entrance_id = cur.lastrowid
            ent_pos = (e.lat, e.lng)

        eatery_pos = (float(place["lat"]), float(place["lng"]))

        points, edges = plan_chain(
            ent_pos,
            eatery_pos,
            [s.model_dump() for s in body.steps],
            body.final_instruction,
            body.final_distance_m,
        )

        # --- node điểm mốc + node quán ---
        node_ids: list[int] = [entrance_id]
        for i, s in enumerate(body.steps, start=1):
            lat, lng = points[i]
            cur.execute(
                "INSERT INTO alley_nodes (place_id, name, lat, lng, node_type, image_url, description, campus) "
                "VALUES (NULL, %s, %s, %s, 'landmark', %s, %s, %s)",
                (s.name.strip(), lat, lng, s.image_url, s.description, campus),
            )
            node_ids.append(cur.lastrowid)

        if eatery_row:
            eatery_id = eatery_row["id"]
        else:
            cur.execute(
                "INSERT INTO alley_nodes (place_id, name, lat, lng, node_type, campus) "
                "SELECT id, name, lat, lng, 'eatery', campus FROM places WHERE id=%s",
                (body.place_id,),
            )
            eatery_id = cur.lastrowid
        node_ids.append(eatery_id)

        # --- cạnh ---
        for ed in edges:
            cur.execute(
                "INSERT INTO alley_edges (from_node_id, to_node_id, distance_m, instruction, is_bidirectional) "
                "VALUES (%s, %s, %s, %s, 1)",
                (node_ids[ed["from"]], node_ids[ed["to"]], ed["distance_m"], ed["instruction"]),
            )

        # Khoảng cách xếp hạng dùng cổng hẻm nếu quán chưa có
        cur.execute(
            "UPDATE places SET alley_entrance_lat=%s, alley_entrance_lng=%s "
            "WHERE id=%s AND alley_entrance_lat IS NULL",
            (ent_pos[0], ent_pos[1], body.place_id),
        )

        conn.commit()
        return {
            "ok": True,
            "entrance_node_id": entrance_id,
            "eatery_node_id": eatery_id,
            "nodes_created": len(node_ids) - (1 if body.entrance_node_id is not None else 0) - (1 if eatery_row else 0),
            "edges_created": len(edges),
        }
    except HTTPException:
        conn.rollback()
        raise
    except Exception as exc:  # noqa: BLE001
        conn.rollback()
        raise HTTPException(500, f"Không lưu được dữ liệu hẻm: {exc}")
    finally:
        cur.close()
        conn.close()
