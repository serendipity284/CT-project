import { req } from './api'; // cần `export` hàm req trong api.ts

const P = '/api/heana';

export type RouteStep = {
  node_id: number; node_name: string; instruction: string; distance_m: number;
  lat: number; lng: number; image_url?: string | null; node_type: string;
};
export type Directions = {
  place_id: number; place_name: string;
  stage1_distance_m: number; stage1_duration_sec: number;
  stage1_polyline: [number, number][]; // [lng, lat]
  stage2: RouteStep[]; stage2_total_m: number;
  has_alley_data: boolean; message: string;
};
export type Entrance = { id: number; name: string; lat: number; lng: number; campus: string };

export type ContributeBody = {
  place_id: number;
  entrance_node_id?: number;
  entrance?: { name: string; lat: number; lng: number; description?: string };
  steps: { name: string; instruction: string; distance_m?: number }[];
  final_instruction: string;
  final_distance_m?: number;
};

export const fetchDirections = (placeId: number, from: { lat: number; lng: number }) =>
  req<Directions>(`${P}/directions`, {
    method: 'POST',
    body: JSON.stringify({ place_id: placeId, user_lat: from.lat, user_lng: from.lng }),
  });

export const fetchEntrances = (campus: string) => req<Entrance[]>(`${P}/alley/entrances?campus=${campus}`);

export const contributeRoute = (body: ContributeBody) =>
  req<{ ok: boolean; edges_created: number }>(`${P}/alley/route`, {
    method: 'POST',
    body: JSON.stringify(body),
  });
