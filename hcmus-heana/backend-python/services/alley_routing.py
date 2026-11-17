"""
HEANA - Alley Graph Routing (2-stage navigation)
Spec 1.5 Giai đoạn 2B + Spatial Reasoning

Chặng 1: GPS Route (OSRM / external) từ user → Alley Entrance
Chặng 2: Landmark Step-by-Step trên đồ thị hẻm (Dijkstra / A*)
"""

from __future__ import annotations

import heapq
import math
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class AlleyNode:
    id: int
    name: str
    lat: float
    lng: float
    node_type: str  # entrance | landmark | eatery
    image_url: Optional[str] = None
    description: Optional[str] = None
    place_id: Optional[int] = None


@dataclass
class AlleyEdge:
    from_id: int
    to_id: int
    distance_m: float
    instruction: str
    image_url: Optional[str] = None


@dataclass
class RouteStep:
    node_id: int
    node_name: str
    instruction: str
    distance_m: float
    lat: float
    lng: float
    image_url: Optional[str] = None
    node_type: str = "landmark"


@dataclass
class AlleyRouteResult:
    found: bool
    total_distance_m: float = 0.0
    steps: list[RouteStep] = field(default_factory=list)
    entrance_node: Optional[AlleyNode] = None
    eatery_node: Optional[AlleyNode] = None
    message: str = ""


class AlleyGraph:
    """Đồ thị hẻm in-memory, xây từ DB."""

    def __init__(self):
        self.nodes: dict[int, AlleyNode] = {}
        self.adj: dict[int, list[tuple[int, float, str, Optional[str]]]] = {}  # to_id, dist, instr, img

    def add_node(self, node: AlleyNode):
        self.nodes[node.id] = node
        if node.id not in self.adj:
            self.adj[node.id] = []

    def add_edge(self, edge: AlleyEdge, bidirectional: bool = True):
        self.adj.setdefault(edge.from_id, []).append(
            (edge.to_id, edge.distance_m, edge.instruction, edge.image_url)
        )
        if bidirectional:
            # Instruction ngược đơn giản
            rev_instr = f"Quay lại hướng {self.nodes.get(edge.from_id).name if edge.from_id in self.nodes else ''}"
            self.adj.setdefault(edge.to_id, []).append(
                (edge.from_id, edge.distance_m, rev_instr, edge.image_url)
            )

    def dijkstra(self, start_id: int, goal_id: int) -> AlleyRouteResult:
        if start_id not in self.nodes or goal_id not in self.nodes:
            return AlleyRouteResult(found=False, message="Node không tồn tại trong đồ thị hẻm.")

        # dist, node_id
        pq: list[tuple[float, int]] = [(0.0, start_id)]
        dist_map: dict[int, float] = {start_id: 0.0}
        prev: dict[int, tuple[int, str, Optional[str], float]] = {}  # node → (prev_node, instr, img, edge_dist)

        while pq:
            d, u = heapq.heappop(pq)
            if u == goal_id:
                break
            if d > dist_map.get(u, math.inf):
                continue
            for v, w, instr, img in self.adj.get(u, []):
                nd = d + w
                if nd < dist_map.get(v, math.inf):
                    dist_map[v] = nd
                    prev[v] = (u, instr, img, w)
                    heapq.heappush(pq, (nd, v))

        if goal_id not in dist_map:
            return AlleyRouteResult(
                found=False,
                message="Không tìm thấy đường đi trong hẻm từ cổng đến quán.",
            )

        # Reconstruct path
        steps: list[RouteStep] = []
        cur = goal_id
        total = dist_map[goal_id]

        # Đi ngược từ goal về start
        chain: list[tuple[int, str, Optional[str], float]] = []
        while cur != start_id:
            if cur not in prev:
                break
            pnode, instr, img, ed = prev[cur]
            chain.append((cur, instr, img, ed))
            cur = pnode
        chain.reverse()

        # Start node
        start_node = self.nodes[start_id]
        steps.append(RouteStep(
            node_id=start_id,
            node_name=start_node.name,
            instruction=f"Bắt đầu từ {start_node.name}",
            distance_m=0.0,
            lat=start_node.lat,
            lng=start_node.lng,
            image_url=start_node.image_url,
            node_type=start_node.node_type,
        ))

        for node_id, instr, img, ed in chain:
            node = self.nodes[node_id]
            steps.append(RouteStep(
                node_id=node_id,
                node_name=node.name,
                instruction=instr,
                distance_m=ed,
                lat=node.lat,
                lng=node.lng,
                image_url=img or node.image_url,
                node_type=node.node_type,
            ))

        return AlleyRouteResult(
            found=True,
            total_distance_m=total,
            steps=steps,
            entrance_node=self.nodes[start_id],
            eatery_node=self.nodes[goal_id],
        )


def find_entrance_for_place(graph: AlleyGraph, place_id: int) -> Optional[AlleyNode]:
    """Tìm node loại 'entrance' gần nhất với quán (hoặc node entrance có liên kết)."""
    eatery_nodes = [n for n in graph.nodes.values() if n.place_id == place_id and n.node_type == "eatery"]
    if not eatery_nodes:
        return None
    # Đơn giản: tìm entrance trong cùng connected component (ở đây giả định 1 entrance chính)
    entrances = [n for n in graph.nodes.values() if n.node_type == "entrance"]
    if not entrances:
        return None
    # Chọn entrance gần eatery nhất theo đường chim bay
    eatery = eatery_nodes[0]
    best = min(
        entrances,
        key=lambda e: math.hypot(e.lat - eatery.lat, e.lng - eatery.lng),
    )
    return best


def build_alley_route(
    graph: AlleyGraph,
    place_id: int,
) -> AlleyRouteResult:
    """
    Xây dựng chặng 2: từ Cổng hẻm → Quán bằng Dijkstra trên alley graph.
    """
    eatery_nodes = [n for n in graph.nodes.values() if n.place_id == place_id and n.node_type == "eatery"]
    if not eatery_nodes:
        return AlleyRouteResult(
            found=False,
            message="Quán này chưa có dữ liệu điểm mốc trong hẻm.",
        )
    eatery = eatery_nodes[0]
    entrance = find_entrance_for_place(graph, place_id)
    if not entrance:
        return AlleyRouteResult(
            found=False,
            message="Không tìm thấy cổng hẻm tương ứng với quán.",
        )
    return graph.dijkstra(entrance.id, eatery.id)


# ------------------------------------------------------------
# Helper: Load graph from DB rows
# ------------------------------------------------------------

def load_graph_from_rows(
    node_rows: list[dict],
    edge_rows: list[dict],
) -> AlleyGraph:
    """
    node_rows: list of dict với keys id, name, lat, lng, node_type, image_url, description, place_id
    edge_rows: list of dict với keys from_node_id, to_node_id, distance_m, instruction, image_url, is_bidirectional
    """
    g = AlleyGraph()
    for r in node_rows:
        g.add_node(AlleyNode(
            id=r["id"],
            name=r["name"],
            lat=float(r["lat"]),
            lng=float(r["lng"]),
            node_type=r["node_type"],
            image_url=r.get("image_url"),
            description=r.get("description"),
            place_id=r.get("place_id"),
        ))
    for r in edge_rows:
        g.add_edge(
            AlleyEdge(
                from_id=r["from_node_id"],
                to_id=r["to_node_id"],
                distance_m=float(r["distance_m"]),
                instruction=r["instruction"],
                image_url=r.get("image_url"),
            ),
            bidirectional=bool(r.get("is_bidirectional", True)),
        )
    return g