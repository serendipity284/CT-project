"""
Logic thuần (không DB) để dựng chuỗi node/edge từ dữ liệu người dùng đóng góp.

Chuỗi: cổng hẻm (0) → điểm mốc 1..n → quán (n+1).
Instruction của cạnh i→i+1 là câu hướng dẫn để ĐI TỚI điểm i+1.
"""

from __future__ import annotations

import math
from typing import Optional


def haversine_m(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    r = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(min(1.0, math.sqrt(a)))


def plan_chain(
    entrance: tuple[float, float],
    eatery: tuple[float, float],
    steps: list[dict],
    final_instruction: str,
    final_distance_m: Optional[float] = None,
) -> tuple[list[tuple[float, float]], list[dict]]:
    """
    Trả về (points, edges).
    points: tọa độ [entrance, step1..stepN, eatery]; điểm mốc không có lat/lng
            được nội suy tuyến tính giữa cổng và quán.
    edges:  [{from, to, distance_m, instruction}] với from/to là chỉ số trong points.
    distance_m: dùng giá trị người dùng nhập, nếu thiếu thì tính theo tọa độ (tối thiểu 1m).
    """
    n = len(steps)
    points: list[tuple[float, float]] = [entrance]
    for i, s in enumerate(steps):
        if s.get("lat") is not None and s.get("lng") is not None:
            points.append((float(s["lat"]), float(s["lng"])))
        else:
            f = (i + 1) / (n + 1)
            points.append(
                (
                    entrance[0] + (eatery[0] - entrance[0]) * f,
                    entrance[1] + (eatery[1] - entrance[1]) * f,
                )
            )
    points.append(eatery)

    instructions = [s["instruction"] for s in steps] + [final_instruction]
    given = [s.get("distance_m") for s in steps] + [final_distance_m]

    edges: list[dict] = []
    for i in range(len(points) - 1):
        d = given[i] or haversine_m(*points[i], *points[i + 1])
        edges.append(
            {
                "from": i,
                "to": i + 1,
                "distance_m": round(max(float(d), 1.0), 1),
                "instruction": instructions[i].strip(),
            }
        )
    return points, edges
