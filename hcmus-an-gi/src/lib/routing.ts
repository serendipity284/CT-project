/** Chỉ đường đi bộ qua OSRM công cộng (không cần API key). */

export type RouteResult = {
  coordinates: [number, number][]; // [lng, lat]
  distanceM: number;
  durationSec: number;
};

export async function fetchWalkingRoute(
  fromLat: number,
  fromLng: number,
  toLat: number,
  toLng: number,
): Promise<RouteResult | null> {
  const url =
    `https://router.project-osrm.org/route/v1/walking/` +
    `${fromLng},${fromLat};${toLng},${toLat}` +
    `?overview=full&geometries=geojson`;
  try {
    const res = await fetch(url);
    if (!res.ok) return null;
    const data = await res.json();
    const route = data?.routes?.[0];
    if (!route?.geometry?.coordinates?.length) return null;
    return {
      coordinates: route.geometry.coordinates as [number, number][],
      distanceM: Math.round(route.distance),
      durationSec: Math.round(route.duration),
    };
  } catch {
    return null;
  }
}
