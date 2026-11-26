import { useEffect, useMemo, useState, type ReactNode } from "react";
import { ArrowLeft } from "lucide-react";
import { CampusMap } from "./CampusMap";
import { CAMPUSES, walkMinutes, type CampusId } from "../lib/campuses";
import { mapsPinUrl, mapsSearchUrl } from "../lib/maps";
import type { Place } from "../lib/places-data";
import type { Review } from "../lib/storage";
import { apiEnabled, fetchGoogleReviews } from "../lib/api";
import AlleyDirections from "./AlleyDirections";
import AlleyContribute from "./AlleyContribute";
import type { Directions } from "../lib/alleyApi";
import { getApiUser } from "../lib/api";
import type { UserLocation } from "../lib/useUserLocation";  
import { walkMinutesFromMeters } from "../lib/geo";   


export type PlaceMode = "detail" | "route";

type Props = {
  mode: PlaceMode;
  place: Place & { meters: number };
  campus: CampusId;
  rating?: { avg: number; count: number };
  reviews: Review[];
  /** Khối thông tin chi tiết (món, giá, giờ, địa chỉ, menu…) do App cung cấp */
  info: ReactNode;
  loc: UserLocation;
  route: {
    coords: [number, number][];
    meta: { distanceM: number; durationSec: number } | null;
    loading: boolean;
    error: string;
  };
  onBack: () => void;
  onSwitch: (m: PlaceMode) => void;
  onBigMap: () => void;
};

type GData = Awaited<ReturnType<typeof fetchGoogleReviews>>;

function GoogleReviews({ placeId }: { placeId: number }) {
  const [data, setData] = useState<GData | null>(null);
  const [status, setStatus] = useState<"loading" | "ok" | "err">("loading");

  useEffect(() => {
    if (!apiEnabled()) return;
    let cancelled = false;
    setStatus("loading");
    fetchGoogleReviews(placeId)
      .then((d) => { if (!cancelled) { setData(d); setStatus("ok"); } })
      .catch(() => { if (!cancelled) setStatus("err"); });
    return () => { cancelled = true; };
  }, [placeId]);

  if (!apiEnabled()) return null;
  return (
    <>
      <h3 className="hx-page-h3">Đánh giá từ Google</h3>
      {status === "loading" && <p className="hx-muted">Đang tải…</p>}
      {status === "err" && <p className="hx-muted">Không tải được đánh giá Google.</p>}
      {status === "ok" && data && !data.found && (
        <p className="hx-muted">Không tìm thấy quán này trên Google Maps.</p>
      )}
      {status === "ok" && data?.found && (
        <>
          <p className="hx-page-sub">
            <span>{data.rating?.toFixed(1)}/5 ★ · {data.count} lượt</span>
          </p>
          {data.reviews.map((r, i) => (
            <p key={i} className="hx-review-line">
              <strong>{r.author}</strong> · {r.rating}/5 · {r.when}
              {r.text ? ` — ${r.text}` : ""}
            </p>
          ))}
          {data.url && (
            <a className="hx-muted" target="_blank" rel="noreferrer" href={data.url}>
              Nguồn: Google Maps
            </a>
          )}
        </>
      )}
    </>
  );
}

/** Trang riêng của 1 quán: "Chi tiết" hoặc "Chỉ đường" (mở từ popup trong chat). */
export function PlacePage({
  mode, place, campus, rating, reviews, info, route, loc, onBack, onSwitch, onBigMap,
}: Props) {
  const origin = CAMPUSES[campus];
  const [alley, setAlley] = useState<Directions | null>(null);
  const [showForm, setShowForm] = useState(false);

  useEffect(() => { setAlley(null); setShowForm(false); }, [place.id]);

// Ghép chặng 1 (OSRM) + chặng 2 (các điểm mốc trong hẻm) thành một đường cho CampusMap
  const mapCoords = useMemo<[number, number][]>(() => {
    if (!alley) return route.coords;
    const s1 = alley.stage1_polyline as [number, number][];
    const s2 = alley.stage2.map((s) => [s.lng, s.lat] as [number, number]);
    const all = [...s1, ...s2];
    return all.length >= 2 ? all : route.coords;
  }, [alley, route.coords]);
  return (
    <div className="hx-app">
      <header className="hx-header">
        <h1 className="hx-logo">HCMUS ĂN GÌ</h1>
      </header>

      <div className="hx-page">
        <div className="hx-page-bar">
          <button type="button" className="hx-back-btn" onClick={onBack}>
            <ArrowLeft size={18} /> Quay lại
          </button>
          <h2 className="hx-page-title">{place.name}</h2>
          <button
            type="button"
            className="hx-switch"
            onClick={() => onSwitch(mode === "detail" ? "route" : "detail")}
          >
            {mode === "detail" ? "Chỉ đường" : "Chi tiết"}
          </button>
        </div>

        {mode === "detail" ? (
          <div className="hx-page-body">
            <p className="hx-page-sub">
              <span>{rating ? `${rating.avg.toFixed(1)}/5 ★ · ${rating.count} lượt` : "Chưa có đánh giá"}</span>
              <span>Cách {origin.short} {place.meters} m · {walkMinutes(place.meters)} phút đi bộ</span>
            </p>
            {info}
            <h3 className="hx-page-h3">Đánh giá</h3>
            {reviews.length === 0 && <p className="hx-muted">Chưa có đánh giá nào.</p>}
            {reviews.slice(0, 5).map((r) => (
              <p key={r.id} className="hx-review-line">
                <strong>{r.authorName}</strong> · {r.rating}/5 — {r.body}
              </p>
            ))}
            <GoogleReviews placeId={place.id} />
          </div>
        ) : (
          <div className="hx-page-body hx-route-body">
            <p className="hx-page-sub">
              {route.loading && <span>Đang tính đường đi bộ…</span>}
              {!route.loading && route.meta && (
                <span>
                  Đi bộ khoảng <strong>{route.meta.distanceM} m</strong> ·{" "}
                  <strong>{walkMinutesFromMeters(route.meta.distanceM)} phút</strong>
                </span>
              )}
              {route.error && <span className="hx-muted">{route.error}</span>}
            </p>
          <div className="loc-bar">
            <button type="button" className="alley-btn" onClick={() => void loc.request()}
              disabled={loc.status === "loading"}>
              {loc.status === "loading" ? "Đang lấy vị trí…" : "📍 Dùng vị trí của tôi"}
            </button>
            {loc.status === "gps" && <span>Đang tính từ vị trí của bạn.</span>}
            {loc.status === "fallback" && <span className="hx-muted">Không lấy được GPS — tính từ {loc.origin.label}.</span>}
            {loc.status === "gps" && <button type="button" className="alley-link" onClick={loc.reset}>Về cổng trường</button>}
          </div>
            <div className="hx-bigmap">
              <CampusMap
                campus={campus}
                places={[place]}
                activeId={place.id}
                routeCoords={mapCoords}
                onPick={() => {}}
              />
            </div>
            {apiEnabled() && (
              <>
                <AlleyDirections
                  placeId={place.id}
                  origin={loc.origin}
                  onResult={(d) => setAlley(d)}
                  onNoData={() => setShowForm(true)}
                />
                {showForm && (getApiUser() ? (
                  <AlleyContribute placeId={place.id} campus={campus} onDone={() => setShowForm(false)} />
                ) : (
                  <p className="hx-muted">Đăng nhập để đóng góp đường đi trong hẻm.</p>
                ))}
              </>
            )}
            <div className="hx-links">
              <a target="_blank" rel="noreferrer"
                href={`https://www.google.com/maps/dir/?api=1&origin=${loc.origin.lat},${loc.origin.lng}&destination=${place.lat},${place.lng}&travelmode=walking`}>
                Mở Google Maps
              </a>
              <a target="_blank" rel="noreferrer" href={mapsSearchUrl(place.address)}>Theo địa chỉ</a>
              <a target="_blank" rel="noreferrer" href={mapsPinUrl(place.lat, place.lng)}>Theo vị trí</a>
              <button type="button" onClick={onBigMap}>Xem cùng các quán khác</button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
