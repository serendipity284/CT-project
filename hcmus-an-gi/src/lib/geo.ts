import { CAMPUSES, type CampusId } from './campuses';

export type LatLng = { lat: number; lng: number };


export function haversineM(a: LatLng, b: LatLng): number {
  const r = 6371000;
  const rad = (x: number) => (x * Math.PI) / 180;
  const dp = rad(b.lat - a.lat);
  const dl = rad(b.lng - a.lng);
  const h =
    Math.sin(dp / 2) ** 2 + Math.cos(rad(a.lat)) * Math.cos(rad(b.lat)) * Math.sin(dl / 2) ** 2;
  return 2 * r * Math.asin(Math.min(1, Math.sqrt(h)));
}

export type Origin = LatLng & { source: 'gps' | 'gate'; label: string };

/** GPS nếu có và trong 15 km quanh trường; ngược lại dùng cổng trường. */
export function resolveOrigin(campus: CampusId, timeoutMs = 6000): Promise<Origin> {
  const gate = CAMPUSES[campus];
  const fallback: Origin = { lat: gate.lat, lng: gate.lng, source: 'gate', label: `cổng trường ${gate.short}` };
  if (typeof navigator === 'undefined' || !navigator.geolocation) return Promise.resolve(fallback);
  return new Promise((resolve) => {
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        const p = { lat: pos.coords.latitude, lng: pos.coords.longitude };
        resolve(
          haversineM(p, gate) > 15000
            ? fallback
            : { ...p, source: 'gps', label: 'Vị trí của bạn' },
        );
      },
      () => resolve(fallback),
      { enableHighAccuracy: true, timeout: timeoutMs, maximumAge: 30000 },
    );
  });
}

/** Đi bộ ~4.8 km/h ≈ 80 m/phút. Dùng thay cho duration của OSRM demo (tính theo xe hơi nên quá nhanh). */
export const WALK_M_PER_MIN = 80;
export const walkMinutesFromMeters = (m: number) => Math.max(1, Math.round(m / WALK_M_PER_MIN));
