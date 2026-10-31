export type CampusId = "q5" | "lang";

export const CAMPUSES: Record<
  CampusId,
  { id: CampusId; label: string; short: string; lat: number; lng: number }
> = {
  q5: {
    id: "q5",
    label: "Cơ sở Nguyễn Văn Cừ, Quận 5",
    short: "Quận 5",
    lat: 10.762622,
    lng: 106.68236,
  },
  lang: {
    id: "lang",
    label: "Làng Đại học, Linh Trung",
    short: "Làng ĐH",
    lat: 10.87005,
    lng: 106.8004,
  },
};

export const BUDGET_PRESETS = [30000, 50000, 80000, 120000];
export const RADIUS_PRESETS = [300, 500, 1000, 2000];

/** Khoảng cách đường chim bay (mét). */
export function haversine(aLat: number, aLng: number, bLat: number, bLng: number) {
  const R = 6371000;
  const dLat = ((bLat - aLat) * Math.PI) / 180;
  const dLng = ((bLng - aLng) * Math.PI) / 180;
  const s =
    Math.sin(dLat / 2) ** 2 +
    Math.cos((aLat * Math.PI) / 180) *
      Math.cos((bLat * Math.PI) / 180) *
      Math.sin(dLng / 2) ** 2;
  return 2 * R * Math.asin(Math.min(1, Math.sqrt(s)));
}

/** Ước lượng phút đi bộ ~75 m/phút. */
export function walkMinutes(meters: number) {
  return Math.max(1, Math.round(meters / 75));
}

export function vnd(n: number) {
  return new Intl.NumberFormat("vi-VN").format(n) + "đ";
}
