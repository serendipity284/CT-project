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
      msg = j.detail ?? j.message ?? JSON.stringify(j);
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
