import { useEffect, useState } from "react";
import { CampusMap } from "./CampusMap";
import { CAMPUSES, vnd, walkMinutes, type CampusId } from "../lib/campuses";
import { mapsPinUrl, mapsSearchUrl, splitAddress } from "../lib/maps";
import type { Place } from "../lib/places-data";
import { fetchWalkingRoute } from "../lib/routing";
import type { Review } from "../lib/storage";

type Props = {
  place: Place & { meters: number };
  campus: CampusId;
  rating?: { avg: number; count: number };
  reviews: Review[];
  onOpenBigMap: () => void;
};

/** Panel mở ra khi bấm vào 1 quán: 2 thanh "Chi tiết" và "Chỉ đường". */
export function PlaceDetail({ place, campus, rating, reviews, onOpenBigMap }: Props) {
  const [tab, setTab] = useState<"detail" | "route">("detail");
  const [coords, setCoords] = useState<[number, number][]>([]);
  const [meta, setMeta] = useState<{ distanceM: number; durationSec: number } | null>(null);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState("");

  // chỉ tính đường khi mở thanh "Chỉ đường"
  useEffect(() => {
    if (tab !== "route") return;
    let cancelled = false;
    const o = CAMPUSES[campus];
    setLoading(true);
    setErr("");
    fetchWalkingRoute(o.lat, o.lng, place.lat, place.lng).then((r) => {
      if (cancelled) return;
      setLoading(false);
      if (!r) {
        setCoords([[o.lng, o.lat], [place.lng, place.lat]]);
        setMeta(null);
        setErr("Không lấy được đường đi bộ, đang hiện đường thẳng.");
        return;
      }
      setCoords(r.coordinates);
      setMeta({ distanceM: r.distanceM, durationSec: r.durationSec });
    });
    return () => {
      cancelled = true;
    };
  }, [tab, campus, place.id, place.lat, place.lng]);

  const { address, note } = splitAddress(place.address);
  const origin = CAMPUSES[campus];

  return (
    <div className="hx-detail">
      <div className="hx-tabs" role="tablist">
        <button type="button" role="tab" aria-selected={tab === "detail"}
          className={tab === "detail" ? "is-on" : ""} onClick={() => setTab("detail")}>
          Chi tiết
        </button>
        <button type="button" role="tab" aria-selected={tab === "route"}
          className={tab === "route" ? "is-on" : ""} onClick={() => setTab("route")}>
          Chỉ đường
        </button>
      </div>

      {tab === "detail" && (
        <dl className="hx-info">
          <dt>Món</dt><dd>{place.cuisine}</dd>
          <dt>Giá</dt>
          <dd>{place.price_max > 0 ? `${vnd(place.price_min)} – ${vnd(place.price_max)}` : "Chưa rõ"}</dd>
          <dt>Giờ mở cửa</dt><dd>{place.hours}</dd>
          <dt>Địa chỉ</dt><dd>{address}{note ? ` (${note})` : ""}</dd>
          <dt>Cách {origin.short}</dt><dd>{place.meters} m · khoảng {walkMinutes(place.meters)} phút đi bộ</dd>
          <dt>Đánh giá</dt>
          <dd>{rating ? `${rating.avg.toFixed(1)}/5 · ${rating.count} lượt` : "Chưa có"}</dd>
          {reviews.slice(0, 2).map((r) => (
            <dd key={r.id} className="hx-review"><strong>{r.authorName}</strong> · {r.rating}/5 — {r.body}</dd>
          ))}
        </dl>
      )}

      {tab === "route" && (
        <div className="hx-route">
          {loading && <p className="hx-muted">Đang tính đường đi bộ…</p>}
          {!loading && meta && (
            <p>
              Đi bộ khoảng <strong>{meta.distanceM} m</strong> ·{" "}
              <strong>{Math.max(1, Math.round(meta.durationSec / 60))} phút</strong>
            </p>
          )}
          {err && <p className="hx-muted">{err}</p>}
          <div className="hx-minimap">
            <CampusMap campus={campus} places={[place]} activeId={place.id} routeCoords={coords} onPick={() => {}} />
          </div>
          <div className="hx-links">
            <a target="_blank" rel="noreferrer"
              href={`https://www.google.com/maps/dir/?api=1&origin=${origin.lat},${origin.lng}&destination=${place.lat},${place.lng}&travelmode=walking`}>
              Mở Google Maps
            </a>
            <a target="_blank" rel="noreferrer" href={mapsSearchUrl(place.address)}>Theo địa chỉ</a>
            <a target="_blank" rel="noreferrer" href={mapsPinUrl(place.lat, place.lng)}>Theo vị trí</a>
            <button type="button" onClick={onOpenBigMap}>Bản đồ lớn</button>
          </div>
        </div>
      )}
    </div>
  );
}
