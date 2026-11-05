/** Client gọi FastAPI + MySQL. Không có VITE_API_URL → dùng offline. */

const BASE = (import.meta.env.VITE_API_URL as string | undefined)?.replace(/\/$/, "") ?? "";

export function apiEnabled() {
  return Boolean(BASE);
}

export function apiBase() {
  return BASE;
}

function authHeaders(): HeadersInit {
  const token = localStorage.getItem("hcmus_api_token");
  return token
    ? { "Content-Type": "application/json", Authorization: `Bearer ${token}` }
    : { "Content-Type": "application/json" };
}

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    ...init,
    headers: { ...authHeaders(), ...(init?.headers ?? {}) },
  });
  if (!res.ok) {
    let msg = res.statusText;
    try {
      const j = await res.json();
      msg = typeof j.detail === "string" ? j.detail : Array.isArray(j.detail) && j.detail[0]?.msg ? j.detail[0].msg : (j.message ?? JSON.stringify(j));
    } catch {
      /* ignore */
    }
    throw new Error(typeof msg === "string" ? msg : "API lỗi");
  }
  return res.json() as Promise<T>;
}

export type ApiPlace = {
  id: number;
  name: string;
  campus: string;
  lat: number;
  lng: number;
  price_min: number;
  price_max: number;
  cuisine: string;
  address: string;
  hours: string;
  meters?: number;
};

export type ApiUser = { id: string; email: string; name: string };

export async function health() {
  return req<{ status: string; mysql: boolean }>("/health");
}

export async function fetchPlaces(campus: string, budget: number, radiusM: number) {
  const q = new URLSearchParams({
    campus,
    budget: String(budget),
    radius_m: String(radiusM),
  });
  return req<ApiPlace[]>(`/places?${q}`);
}

export async function signup(email: string, password: string, name: string) {
  const data = await req<{ token: string; user: ApiUser }>("/auth/signup", {
    method: "POST",
    body: JSON.stringify({ email, password, name }),
  });
  localStorage.setItem("hcmus_api_token", data.token);
  localStorage.setItem("hcmus_api_user", JSON.stringify(data.user));
  return data;
}

export async function login(email: string, password: string) {
  const data = await req<{ token: string; user: ApiUser }>("/auth/login", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
  localStorage.setItem("hcmus_api_token", data.token);
  localStorage.setItem("hcmus_api_user", JSON.stringify(data.user));
  return data;
}

export function logoutApi() {
  localStorage.removeItem("hcmus_api_token");
  localStorage.removeItem("hcmus_api_user");
}

export function getApiUser(): ApiUser | null {
  try {
    const raw = localStorage.getItem("hcmus_api_user");
    return raw ? (JSON.parse(raw) as ApiUser) : null;
  } catch {
    return null;
  }
}

export async function fetchReviews(placeId?: number) {
  const q = placeId != null ? `?place_id=${placeId}` : "";
  return req<
    {
      id: number;
      place_id: number;
      rating: number;
      body: string;
      created_at: string;
      author_name: string;
    }[]
  >(`/reviews${q}`);
}

export async function postReview(placeId: number, rating: number, body: string) {
  return req<{ ok: boolean }>("/reviews", {
    method: "POST",
    body: JSON.stringify({ place_id: placeId, rating, body }),
  });
}

export async function fetchSaves() {
  return req<number[]>("/saves");
}

export async function toggleSaveApi(placeId: number) {
  return req<{ saved: boolean }>(`/saves/${placeId}`, { method: "POST" });
}

export async function fetchHistory() {
  return req<
    {
      id: number;
      campus: string;
      budget: number;
      radius_m: number;
      query: string;
      created_at: string;
    }[]
  >("/history");
}

export async function postHistory(campus: string, budget: number, radiusM: number, query: string) {
  return req<{ ok: boolean }>("/history", {
    method: "POST",
    body: JSON.stringify({ campus, budget, radius_m: radiusM, query }),
  });
}

export async function postChat(
  message: string,
  slots: { campus?: string; budget?: number; radius_m?: number },
) {
  return req<{
    ready: boolean;
    campus?: string;
    budget?: number;
    radius_m?: number;
    reply: string;
  }>("/chat", {
    method: "POST",
    body: JSON.stringify({ message, ...slots }),
  });
}


export type ContributeBody = {
  name: string;
  campus: string;
  lat?: number; // bỏ trống → server tự định vị theo địa chỉ
  lng?: number;
  maps_url?: string; // link Google Maps (tùy chọn) → server lấy tọa độ chính xác
  price_min?: number; // bỏ trống → AI/server tự tính từ giá các món
  price_max?: number;
  cuisine: string;
  address: string;
  hours: string;
  note?: string;
  menu_meta?: { phone?: string | null; hours?: string | null; notes?: string | null };
};

export async function contributePlace(body: ContributeBody) {
  return req<{ ok: boolean; id: number; lat: number; lng: number; approx_location: boolean; location_source: "client" | "maps_link" | "address"; rate_limit?: unknown }>("/places/contribute", {
    method: "POST",
    body: JSON.stringify(body),
  });
}


export type ScannedDish = {
  name: string;
  price: number | null;
  category?: string | null;
  note?: string | null;
};

export type ScanResult = {
  ok: boolean;
  images: number;
  restaurant_hint?: string | null;
  phone?: string | null;
  hours?: string | null;
  address_hint?: string | null;
  dishes: ScannedDish[];
  notes?: string[];
  raw_notes?: string | null;
};

/** Gửi 1..10 ảnh (các trang của cùng một menu) để AI đọc một lần. */
export async function scanMenuImages(files: File[]): Promise<ScanResult> {
  const token = localStorage.getItem("hcmus_api_token");
  const fd = new FormData();
  files.forEach((f) => fd.append("files", f));
  const res = await fetch(`${BASE}/menu/scan`, {
    method: "POST",
    headers: token ? { Authorization: `Bearer ${token}` } : {},
    body: fd,
  });
  if (!res.ok) {
    let msg = res.statusText;
    try {
      const j = await res.json();
      msg = j.detail ?? JSON.stringify(j);
    } catch { /* */ }
    throw new Error(typeof msg === "string" ? msg : "Scan menu loi");
  }
  return res.json() as Promise<ScanResult>;
}

export async function contributeWithMenu(body: ContributeBody & { dishes: ScannedDish[] }) {
  return req<{ ok: boolean; id: number; lat: number; lng: number; approx_location: boolean; location_source: "client" | "maps_link" | "address"; dishes_saved: number }>("/places/contribute-with-menu", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function fetchDishes(placeId: number) {
  return req<{ id: number; name: string; price: number | null; note: string | null }[]>(
    `/places/${placeId}/dishes`,
  );
}

export type ApiDish = {
  id: number;
  name: string;
  category?: string | null;
  price: number | null;
  note: string | null;
};
export type ApiMenuMeta = { phone: string | null; hours: string | null; notes: string | null };
export type ApiPlaceInfo = { dishes: ApiDish[]; menu_meta: ApiMenuMeta | null };
export type ApiSavedPlace = ApiPlace & { dishes: ApiDish[]; menu_meta?: ApiMenuMeta | null };

/** Menu + thông tin AI đọc từ ảnh menu của một quán. */
export async function fetchPlaceInfo(placeId: number) {
  return req<ApiPlaceInfo>(`/places/${placeId}/info`);
}

/** Quán đã lưu của user: đủ thông tin + menu, không lọc theo bán kính. */
export async function fetchSavedPlaces() {
  return req<ApiSavedPlace[]>("/places/saved");
}
