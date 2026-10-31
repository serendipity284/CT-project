import { CAMPUSES, type CampusId } from "./campuses";
import type { Place } from "./places-data";
import { PLACES } from "./places-data";

const CUISINES = [
  "Cơm",
  "Phở",
  "Bún",
  "Mì",
  "Bánh mì",
  "Xôi",
  "Chay",
  "Nước",
  "Ăn vặt",
  "Lẩu",
  "Hủ tiếu",
  "Cháo",
];

const PREFIX = ["Cô", "Chú", "Anh", "Chị", "Quán", "Nhà", "Góc", "Hẻm"];
const NAMES = ["Ba", "Tư", "Năm", "Sáu", "Bảy", "Mai", "Lan", "Hùng", "Minh", "An", "Vy", "Khoa"];

function rand(min: number, max: number) {
  return min + Math.random() * (max - min);
}

function pick<T>(arr: T[]): T {
  return arr[Math.floor(Math.random() * arr.length)]!;
}

/** Tạo bộ quán mẫu mới quanh 2 cơ sở (toạ độ ngẫu nhiên trong ~1.2km). */
export function generatePlaces(seed?: number): Place[] {
  const rng = seed ?? Date.now();
  // xáo trộn nhẹ theo seed
  Math.sin(rng);
  const out: Place[] = [];
  let id = 1;
  for (const campus of Object.keys(CAMPUSES) as CampusId[]) {
    const c = CAMPUSES[campus];
    const count = 8;
    for (let i = 0; i < count; i++) {
      // ~±0.008 độ ≈ 800–900m
      const lat = c.lat + rand(-0.008, 0.008);
      const lng = c.lng + rand(-0.008, 0.008);
      const cuisine = pick(CUISINES);
      const lo = Math.round(rand(15, 45)) * 1000;
      const hi = lo + Math.round(rand(5, 40)) * 1000;
      out.push({
        id: id++,
        name: `${pick(PREFIX)} ${pick(NAMES)} ${cuisine.toLowerCase()}`,
        campus,
        lat: Number(lat.toFixed(6)),
        lng: Number(lng.toFixed(6)),
        price_min: lo,
        price_max: hi,
        cuisine,
        address: campus === "q5" ? "Gần Nguyễn Văn Cừ, Q.5" : "Gần Làng Đại học, Linh Trung",
        hours: pick(["6:00–14:00", "7:00–21:00", "10:00–22:00", "16:00–23:00", "6:30–20:00"]),
      });
    }
  }
  return out;
}

export function initialPlaces(): Place[] {
  return PLACES.map((p) => ({ ...p }));
}
