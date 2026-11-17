/**
 * HEANA Frontend Ranking (client-side fallback / demo mode)
 * Mirror logic của backend services/ranking.py
 */

import type { Dish, PlaceResult, UserPreference } from "./heana-types";

export interface RawPlace {
  id: number;
  name: string;
  campus: "q5" | "lang";
  address: string;
  lat: number;
  lng: number;
  alley_entrance_lat?: number | null;
  alley_entrance_lng?: number | null;
  open_time?: string | null; // "06:00"
  close_time?: string | null;
  hours_text?: string;
  price_min: number;
  price_max: number;
  cuisine: string;
  rating_avg: number;
  rating_count: number;
  updated_at?: string;
  image_url?: string | null;
  dishes?: Dish[];
}

function haversine(lat1: number, lng1: number, lat2: number, lng2: number): number {
  const R = 6371000;
  const toRad = (d: number) => (d * Math.PI) / 180;
  const dLat = toRad(lat2 - lat1);
  const dLng = toRad(lng2 - lng1);
  const a =
    Math.sin(dLat / 2) ** 2 +
    Math.cos(toRad(lat1)) * Math.cos(toRad(lat2)) * Math.sin(dLng / 2) ** 2;
  return 2 * R * Math.asin(Math.min(1, Math.sqrt(a)));
}

function normalize(s: string) {
  return s.trim().toLowerCase();
}

function hasAllergyConflict(ingredients: string[], allergies: string[]): boolean {
  if (!allergies.length) return false;
  const ing = new Set(ingredients.map(normalize));
  return allergies.some((a) => ing.has(normalize(a)));
}

function parseTime(t?: string | null): { h: number; m: number } | null {
  if (!t) return null;
  const m = t.match(/(\d{1,2}):(\d{2})/);
  if (!m) return null;
  return { h: Number(m[1]), m: Number(m[2]) };
}

function isOpenNow(open?: string | null, close?: string | null, now = new Date()): boolean {
  const o = parseTime(open);
  const c = parseTime(close);
  if (!o || !c) return true;
  const mins = now.getHours() * 60 + now.getMinutes();
  const openM = o.h * 60 + o.m;
  const closeM = c.h * 60 + c.m;
  if (openM <= closeM) return mins >= openM && mins <= closeM;
  return mins >= openM || mins <= closeM; // overnight
}

function bayesian(avg: number, count: number, priorAvg = 3.5, priorCount = 10) {
  return (priorAvg * priorCount + avg * count) / (priorCount + count);
}

function freshness(updatedAt?: string, maxDays = 120): number {
  if (!updatedAt) return 0.5;
  const days = (Date.now() - new Date(updatedAt).getTime()) / 86400000;
  if (days <= 0) return 1;
  return Math.max(0, 1 - days / maxDays);
}

export function hardFilterAndRank(
  places: RawPlace[],
  preference: UserPreference,
  userLat: number,
  userLng: number,
  opts: {
    requiredDish?: string;
    maxPrice?: number;
    maxRadiusM?: number;
    topK?: number;
  } = {},
): PlaceResult[] {
  const { requiredDish, maxPrice, maxRadiusM = 2000, topK = 15 } = opts;
  const req = (requiredDish || "").trim().toLowerCase();
  const allergies = preference.allergies || [];

  const candidates: PlaceResult[] = [];

  for (const p of places) {
    if (!isOpenNow(p.open_time, p.close_time)) continue;

    const dishes = p.dishes || [];
    const validDishes: Dish[] = [];

    for (const d of dishes) {
      if (hasAllergyConflict(d.ingredients || [], allergies)) continue;
      if (req && !d.dish_name.toLowerCase().includes(req) && !p.cuisine.toLowerCase().includes(req)) {
        continue;
      }
      if (maxPrice != null && d.price > maxPrice) continue;
      validDishes.push(d);
    }

    if (req && validDishes.length === 0) continue;
    if (dishes.length > 0 && validDishes.length === 0) continue;

    const tLat = p.alley_entrance_lat ?? p.lat;
    const tLng = p.alley_entrance_lng ?? p.lng;
    const dist = haversine(userLat, userLng, tLat, tLng);

    const priceMin = validDishes.length
      ? Math.min(...validDishes.map((d) => d.price))
      : p.price_min;
    const priceMax = validDishes.length
      ? Math.max(...validDishes.map((d) => d.price))
      : p.price_max;

    candidates.push({
      place_id: p.id,
      name: p.name,
      campus: p.campus,
      address: p.address,
      lat: p.lat,
      lng: p.lng,
      alley_entrance_lat: p.alley_entrance_lat,
      alley_entrance_lng: p.alley_entrance_lng,
      hours_text: p.hours_text || "",
      price_min: priceMin,
      price_max: priceMax,
      cuisine: p.cuisine,
      rating_avg: p.rating_avg,
      rating_count: p.rating_count,
      distance_m: Math.round(dist),
      score: 0,
      matched_dishes: validDishes,
      image_url: p.image_url,
      s_feedback: 0,
      s_price: 0,
      s_distance: 0,
      s_freshness: 0,
    });
  }

  if (!candidates.length) return [];

  // Soft scores
  const totalW =
    preference.w_price + preference.w_distance + preference.w_quality + preference.w_freshness || 1;
  const wPrice = preference.w_price / totalW;
  const wDist = preference.w_distance / totalW;
  const wQual = preference.w_quality / totalW;
  const wFresh = preference.w_freshness / totalW;

  const prices = candidates.map((c) =>
    c.matched_dishes.length
      ? c.matched_dishes.reduce((s, d) => s + d.price, 0) / c.matched_dishes.length
      : (c.price_min + c.price_max) / 2,
  );
  const minP = Math.min(...prices);
  const maxP = Math.max(...prices);
  const rangeP = Math.max(maxP - minP, 1);

  const dists = candidates.map((c) => c.distance_m);
  const minD = Math.min(...dists);
  const maxD = Math.max(Math.max(...dists), maxRadiusM);
  const rangeD = Math.max(maxD - minD, 1);

  for (let i = 0; i < candidates.length; i++) {
    const c = candidates[i];
    const bayes = bayesian(c.rating_avg, c.rating_count);
    c.s_feedback = Math.max(0, Math.min(1, (bayes - 1) / 4));
    c.s_price = 1 - (prices[i] - minP) / rangeP;
    c.s_distance = 1 - (c.distance_m - minD) / rangeD;
    if (c.distance_m > maxRadiusM) c.s_distance *= 0.3;
    c.s_freshness = freshness((places.find((x) => x.id === c.place_id) as any)?.updated_at);
    c.score =
      wQual * c.s_feedback + wPrice * c.s_price + wDist * c.s_distance + wFresh * c.s_freshness;
  }

  candidates.sort((a, b) => b.score - a.score);
  return candidates.slice(0, topK);
}

/** Chuyển importance 1-5 thành preference weights */
export function preferenceFromSurvey(answers: {
  price_importance: number;
  distance_importance: number;
  quality_importance: number;
  allergies_text: string;
}): UserPreference {
  const { price_importance: p, distance_importance: d, quality_importance: q } = answers;
  const total = p + d + q || 3;
  return {
    w_price: +(p / (total + 1.5)).toFixed(3),
    w_distance: +(d / (total + 1.5)).toFixed(3),
    w_quality: +(q / (total + 1.5)).toFixed(3),
    w_freshness: +(1.5 / (total + 1.5)).toFixed(3),
    allergies: answers.allergies_text
      .split(/[,;]/)
      .map((s) => s.trim().toLowerCase())
      .filter(Boolean),
    survey_done: true,
  };
}