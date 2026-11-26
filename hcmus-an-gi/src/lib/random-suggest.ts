import type { Place } from "./places-data";
import type { UserPreference } from "./heana-types";
import { hardFilterAndRank, type RawPlace } from "./heana-ranking";

export type Suggestion = {
  place: Place;
  score: number;   // điểm S theo trọng số khảo sát
  prob: number;    // xác suất được bốc (0-1)
  reason: string;  // câu giải thích
};

/** Softmax: điểm cao -> xác suất cao, nhưng quán điểm thấp vẫn có cơ hội. T nhỏ = ít ngẫu nhiên. */
export function softmax(scores: number[], T = 0.15): number[] {
  const max = Math.max(...scores); // trừ max để tránh tràn số
  const exps = scores.map((s) => Math.exp((s - max) / T));
  const sum = exps.reduce((a, b) => a + b, 0);
  return exps.map((e) => e / sum);
}

/** Roulette wheel: random r trong [0,1) rồi cộng dồn xác suất. */
export function weightedPick<T>(items: T[], probs: number[], rng = Math.random): number {
  const r = rng();
  let acc = 0;
  for (let i = 0; i < items.length; i++) {
    acc += probs[i];
    if (r < acc) return i;
  }
  return items.length - 1;
}

/** Yếu tố đóng góp nhiều nhất vào điểm của quán -> câu giải thích. */
function explain(
  pref: UserPreference,
  s: { s_price: number; s_distance: number; s_feedback: number },
): string {
  if (!pref.survey_done) return "Bạn chưa làm khảo sát nên mình cân nhắc đều giá, khoảng cách và đánh giá.";
  const parts = [
    { w: pref.w_price * s.s_price, text: "giá khá mềm so với các quán xung quanh" },
    { w: pref.w_distance * s.s_distance, text: "nằm gần bạn" },
    { w: pref.w_quality * s.s_feedback, text: "được đánh giá tốt" },
  ];
  parts.sort((a, b) => b.w - a.w);
  return `Mình chọn quán này vì ${parts[0].text}, hợp với ưu tiên trong khảo sát của bạn.`;
}

/**
 * Bốc ngẫu nhiên `count` quán (mặc định 5), KHÔNG trùng nhau trong cùng một lượt.
 * Mỗi lượt bốc dùng softmax trên các quán còn lại (roulette wheel), nên quán điểm cao
 * thường nằm đầu danh sách nhưng quán điểm thấp vẫn có cơ hội lọt vào.
 * Ưu tiên quán chưa gợi ý (excludeIds); nếu không đủ `count` thì bù thêm từ các quán đã gợi ý.
 */

type Ratings = Record<number, { avg: number; count: number }>;

/** Đổi true -> false nếu muốn giá CAO xếp trước. */
const PRICE_CHEAP_FIRST = true;

/**
 * Sắp xếp theo mức quan tâm của khách (trọng số khảo sát):
 * tiêu chí có trọng số lớn nhất là tiêu chí chính, bằng nhau thì xét tiêu chí tiếp theo.
 *  - price:    giá min (quán chưa có giá xếp cuối)
 *  - distance: số mét tới cơ sở (gần xếp trước)
 *  - quality:  điểm đánh giá trung bình (cao xếp trước)
 * Nếu 3 trọng số bằng nhau (khảo sát "Sao cũng được" hoặc chưa làm) thì giữ nguyên thứ tự bốc.
 */
function sortByPreference(
    list: Suggestion[],
    ratings: Ratings,
    pref: UserPreference,
): Suggestion[] {
    const num = (a: number, b: number) => (a === b ? 0 : a - b);

    const criteria = [
        {
            w: pref.w_price,
            cmp: (a: Suggestion, b: Suggestion) => {
                const pa = a.place.price_max > 0 ? a.place.price_min : Infinity;
                const pb = b.place.price_max > 0 ? b.place.price_min : Infinity;
                if (pa === Infinity || pb === Infinity) return num(pa === Infinity ? 1 : 0, pb === Infinity ? 1 : 0);
                return PRICE_CHEAP_FIRST ? num(pa, pb) : num(pb, pa);
            },
        },
        {
            w: pref.w_distance,
            cmp: (a: Suggestion, b: Suggestion) =>
                num(
                    (a.place as Place & { meters: number }).meters,
                    (b.place as Place & { meters: number }).meters,
                ),
        },
        {
            w: pref.w_quality,
            cmp: (a: Suggestion, b: Suggestion) =>
                num(ratings[b.place.id]?.avg ?? 0, ratings[a.place.id]?.avg ?? 0),
        },
    ];

    const ws = criteria.map((c) => c.w);
    if (Math.max(...ws) - Math.min(...ws) < 1e-6) return list; // không có ưu tiên rõ ràng

    // sort ổn định: trọng số lớn trước; trọng số bằng nhau giữ thứ tự price -> distance -> quality
    const ordered = [...criteria].sort((a, b) => b.w - a.w);
    return [...list].sort((a, b) => {
        for (const c of ordered) {
            const d = c.cmp(a, b);
            if (d) return d;
        }
        return 0;
    });
}
export function suggestRandomPlaces(
  candidates: (Place & { meters: number })[], // chính là `ranked` trong App.tsx
  ratings: Record<number, { avg: number; count: number }>,
  pref: UserPreference,
  origin: { lat: number; lng: number },
  radiusM: number,
  excludeIds: number[] = [],
  count = 5,
  T = 0.15,
  rng = Math.random,
): Suggestion[] {
  const scored = scoreCandidates(candidates, ratings, pref, origin, radiusM);
  if (!scored.length) return [];

  const excluded = new Set(excludeIds);
  const fresh = scored.filter((s) => !excluded.has(s.place_id));
  const seen = scored.filter((s) => excluded.has(s.place_id));

  const out: Suggestion[] = [];
  // Rút lần lượt từ `pool` cho tới khi đủ `count` hoặc hết quán
  const drawFrom = (pool: typeof scored) => {
    const rest = [...pool];
    while (rest.length && out.length < count) {
      const probs = softmax(rest.map((s) => s.score), T);
      const i = weightedPick(rest, probs, rng);
      const chosen = rest.splice(i, 1)[0];
      const place = candidates.find((p) => p.id === chosen.place_id)!;
      out.push({ place, score: chosen.score, prob: probs[i], reason: explain(pref, chosen) });
    }
  };
  drawFrom(fresh);
  if (out.length < count) drawFrom(seen); // hết quán mới -> bù từ quán cũ

    return sortByPreference(out, ratings, pref);
}

/** Map Place -> RawPlace rồi chấm điểm bằng công thức có sẵn trong heana-ranking. */
function scoreCandidates(
  candidates: (Place & { meters: number })[],
  ratings: Record<number, { avg: number; count: number }>,
  pref: UserPreference,
  origin: { lat: number; lng: number },
  radiusM: number,
) {
  if (!candidates.length) return [];
  const raw: RawPlace[] = candidates.map((p) => ({
    id: p.id, name: p.name, campus: p.campus, address: p.address,
    lat: p.lat, lng: p.lng, hours_text: p.hours,
    price_min: p.price_min, price_max: p.price_max, cuisine: p.cuisine,
    rating_avg: ratings[p.id]?.avg ?? 0,
    rating_count: ratings[p.id]?.count ?? 0,
    image_url: p.image_url,
  }));
  return hardFilterAndRank(raw, pref, origin.lat, origin.lng, {
    maxRadiusM: radiusM, topK: 100,
  });
}

export function suggestRandomPlace(
  candidates: (Place & { meters: number })[], // chính là `ranked` trong App.tsx (đã lọc campus/ngân sách/bán kính)
  ratings: Record<number, { avg: number; count: number }>,
  pref: UserPreference,
  origin: { lat: number; lng: number },
  radiusM: number,
  excludeIds: number[] = [],
  T = 0.15,
  rng = Math.random,
): Suggestion | null {
  if (!candidates.length) return null;

  // Map Place -> RawPlace để tái dùng công thức điểm có sẵn
  const raw: RawPlace[] = candidates.map((p) => ({
    id: p.id, name: p.name, campus: p.campus, address: p.address,
    lat: p.lat, lng: p.lng, hours_text: p.hours,
    price_min: p.price_min, price_max: p.price_max, cuisine: p.cuisine,
    rating_avg: ratings[p.id]?.avg ?? 0,
    rating_count: ratings[p.id]?.count ?? 0,
    image_url: p.image_url,
  }));

  const scored = hardFilterAndRank(raw, pref, origin.lat, origin.lng, {
    maxRadiusM: radiusM, topK: 100,
  });
  if (!scored.length) return null;

  // Bỏ các quán đã gợi ý; nếu hết quán thì cho random lại từ đầu
  let pool = scored.filter((s) => !excludeIds.includes(s.place_id));
  if (!pool.length) pool = scored;

  const probs = softmax(pool.map((s) => s.score), T);
  const i = weightedPick(pool, probs, rng);
  const chosen = pool[i];
  const place = candidates.find((p) => p.id === chosen.place_id)!;

  return { place, score: chosen.score, prob: probs[i], reason: explain(pref, chosen) };
}