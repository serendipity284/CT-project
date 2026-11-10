import { useCallback, useEffect, useMemo, useState } from "react";
import { Bookmark, RefreshCw, Send } from "lucide-react";
import {
  BUDGET_PRESETS,
  CAMPUSES,
  RADIUS_PRESETS,
  haversine,
  vnd,
  walkMinutes,
  type CampusId,
} from "./lib/campuses";
import { replyFor, type ChatTurn, type Intent } from "./lib/chat-intent";
import type { Place } from "./lib/places-data";
import { generatePlaces, initialPlaces } from "./lib/places-generator";
import { fetchWalkingRoute } from "./lib/routing";
import {
  apiEnabled,
  fetchHistory as apiFetchHistory,
  fetchPlaces as apiFetchPlaces,
  fetchReviews as apiFetchReviews,
  fetchSaves as apiFetchSaves,
  getApiUser,
  health as apiHealth,
  login as apiLogin,
  logoutApi,
  postHistory as apiPostHistory,
  postReview as apiPostReview,
  signup as apiSignup,
  toggleSaveApi,
  contributePlace,
  postChat,
  scanMenuImages,
  contributeWithMenu,
  fetchPlaceInfo,
  fetchSavedPlaces,
  type ApiDish,
  type ApiMenuMeta,
  type ApiPlaceInfo,
  type ApiSavedPlace,
  type EmotionContext,
  type ScannedDish,
} from "./lib/api";
import { mapsPinUrl, mapsSearchUrl, splitAddress } from "./lib/maps";
import { shrinkImage } from "./lib/image";
import {
  addHistory,
  addReview,
  getCurrentUser,
  getHistory,
  getReviews,
  getSaves,
  signIn,
  signOut,
  signUp,
  toggleSave,
  addContribution,
  getContributions,
  type HistoryItem,
  type Review,
  type User,
} from "./lib/storage";
import { CampusMap } from "./components/CampusMap";

type SavedPlace = Place & { dishes: ApiDish[]; menu_meta?: ApiMenuMeta | null };
type MenuFile = { file: File; url: string };
type ScanMeta = { phone: string; hours: string; notes: string };

export default function App() {
  const useApi = apiEnabled();
  const [mysqlOk, setMysqlOk] = useState<boolean | null>(null);
  const [apiError, setApiError] = useState("");
  const [user, setUser] = useState<User | null>(null);
  const [places, setPlaces] = useState<Place[]>(() => initialPlaces());
  const [reviews, setReviews] = useState<Review[]>([]);
  const [saved, setSaved] = useState<number[]>([]);
  const [history, setHistory] = useState<HistoryItem[]>([]);
  const [campus, setCampus] = useState<CampusId>("q5");
  const [budget, setBudget] = useState(50000);
  const [radius, setRadius] = useState(800);
  const [onlySaved, setOnlySaved] = useState(false);
  const [activeId, setActiveId] = useState<number | null>(null);
  const [tab, setTab] = useState<"list" | "chat" | "me" | "contribute">("list");
  const [intent, setIntent] = useState<Intent>({});
  const [turns, setTurns] = useState<ChatTurn[]>([
    {
      role: "bot",
      text: 'Nói quán bạn cần. Ví dụ: "quận 5, dưới 40k, trong 500m". Thiếu ý nào mình hỏi lại.',
    },
  ]);
  const [draft, setDraft] = useState("");
  const [note, setNote] = useState("");
  const [stars, setStars] = useState(5);
  const [page, setPage] = useState<"home" | "login">("home");
  const [routeCoords, setRouteCoords] = useState<[number, number][]>([]);
  const [routeMeta, setRouteMeta] = useState<{ distanceM: number; durationSec: number } | null>(
    null,
  );
  const [routeLoading, setRouteLoading] = useState(false);
  const [routeError, setRouteError] = useState("");
  const [regenMsg, setRegenMsg] = useState("");
  const [contribName, setContribName] = useState("");
  const [contribCuisine, setContribCuisine] = useState("Cơm");
  const [contribAddress, setContribAddress] = useState("");
  const [contribHours, setContribHours] = useState("7:00–20:00");
  const [contribMin, setContribMin] = useState(""); // bỏ trống → AI tự tính
  const [contribMax, setContribMax] = useState("");
  const [contribNote, setContribNote] = useState("");
  const [contribMapsUrl, setContribMapsUrl] = useState("");
  const [contribOffsetM, setContribOffsetM] = useState(200);
  const [contribMsg, setContribMsg] = useState("");
  const [contribBusy, setContribBusy] = useState(false);
  const [scannedDishes, setScannedDishes] = useState<ScannedDish[]>([]);
  const [scanBusy, setScanBusy] = useState(false);
  const [menuFiles, setMenuFiles] = useState<MenuFile[]>([]);
  const [scanMeta, setScanMeta] = useState<ScanMeta | null>(null);
  const [activeInfo, setActiveInfo] = useState<ApiPlaceInfo>({ dishes: [], menu_meta: null });
  const [savedApi, setSavedApi] = useState<ApiSavedPlace[]>([]);
  const [viewSavedId, setViewSavedId] = useState<number | null>(null);
  // Emotion context from server – persisted across chat turns
  const [emotionCtx, setEmotionCtx] = useState<EmotionContext>(null);
  const [emotionTurn, setEmotionTurn] = useState<number | undefined>(undefined);
  const [turnCount, setTurnCount] = useState(0);

  const loadFromApi = useCallback(async () => {
    if (!useApi) return;
    setApiError("");
    try {
      const h = await apiHealth();
      setMysqlOk(h.mysql);
      const list = await apiFetchPlaces(campus, budget, radius);
      setPlaces(
        list.map((p) => ({
          id: p.id,
          name: p.name,
          campus: p.campus as CampusId,
          lat: p.lat,
          lng: p.lng,
          price_min: p.price_min,
          price_max: p.price_max,
          cuisine: p.cuisine,
          address: p.address,
          hours: p.hours,
        })),
      );
      const revs = await apiFetchReviews();
      setReviews(
        revs.map((r) => ({
          id: r.id,
          placeId: r.place_id,
          authorName: r.author_name,
          rating: r.rating,
          body: r.body,
          createdAt: String(r.created_at),
        })),
      );
    } catch (e) {
      setMysqlOk(false);
      setApiError(e instanceof Error ? e.message : "Không gọi được API");
    }
  }, [useApi, campus, budget, radius]);

  useEffect(() => {
    if (useApi) {
      setUser(getApiUser());
      loadFromApi();
    } else {
      setUser(getCurrentUser());
      setReviews(getReviews());
      const contribs = getContributions();
      if (contribs.length) {
        setPlaces((prev) => {
          const extra = contribs.map((c) => ({
            id: c.id,
            name: c.name,
            campus: c.campus,
            lat: c.lat,
            lng: c.lng,
            price_min: c.price_min,
            price_max: c.price_max,
            cuisine: c.cuisine,
            address: c.address,
            hours: c.hours,
          }));
          const ids = new Set(extra.map((e) => e.id));
          return [...extra, ...prev.filter((p) => !ids.has(p.id))];
        });
      }
    }
  }, [useApi, loadFromApi]);

  useEffect(() => {
    if (!user) {
      setSaved([]);
      setHistory([]);
      return;
    }
    if (useApi) {
      (async () => {
        try {
          setSaved(await apiFetchSaves());
          const h = await apiFetchHistory();
          setHistory(
            h.map((x) => ({
              id: x.id,
              campus: x.campus,
              budget: x.budget,
              radiusM: x.radius_m,
              query: x.query,
              createdAt: String(x.created_at),
            })),
          );
        } catch {
          /* token hết hạn */
        }
      })();
    } else {
      setSaved(getSaves(user.id));
      setHistory(getHistory(user.id));
    }
  }, [user, useApi]);

  const ranked = useMemo(() => {
    const origin = CAMPUSES[campus];
    return places
      .map((p) => ({
        ...p,
        meters: Math.round(haversine(origin.lat, origin.lng, p.lat, p.lng)),
      }))
      .filter((p) => p.campus === campus)
      .filter((p) => p.price_min <= budget)
      .filter((p) => p.meters <= radius)
      .filter((p) => !onlySaved || saved.includes(p.id))
      .sort((a, b) => a.meters - b.meters);
  }, [places, campus, budget, radius, onlySaved, saved]);

  const active: (Place & { meters: number }) | null =
    ranked.find((p) => p.id === activeId) ?? ranked[0] ?? null;

  useEffect(() => {
    if (!active) {
      setRouteCoords([]);
      setRouteMeta(null);
      setRouteError("");
      return;
    }
    let cancelled = false;
    const origin = CAMPUSES[campus];
    setRouteLoading(true);
    setRouteError("");
    fetchWalkingRoute(origin.lat, origin.lng, active.lat, active.lng).then((r) => {
      if (cancelled) return;
      setRouteLoading(false);
      if (!r) {
        setRouteCoords([
          [origin.lng, origin.lat],
          [active.lng, active.lat],
        ]);
        setRouteMeta(null);
        setRouteError("Không lấy được đường đi bộ OSRM — đang hiện đường thẳng.");
        return;
      }
      setRouteCoords(r.coordinates);
      setRouteMeta({ distanceM: r.distanceM, durationSec: r.durationSec });
      setRouteError("");
    });
    return () => {
      cancelled = true;
    };
  }, [active?.id, campus, active?.lat, active?.lng]);

  useEffect(() => {
    const empty: ApiPlaceInfo = { dishes: [], menu_meta: null };
    if (!useApi || !active) {
      setActiveInfo(empty);
      return;
    }
    let cancelled = false;
    fetchPlaceInfo(active.id)
      .then((d) => !cancelled && setActiveInfo(d))
      .catch(() => !cancelled && setActiveInfo(empty));
    return () => {
      cancelled = true;
    };
  }, [useApi, active?.id]);

  useEffect(() => {
    if (!useApi || !user) {
      setSavedApi([]);
      return;
    }
    fetchSavedPlaces()
      .then(setSavedApi)
      .catch(() => setSavedApi([]));
  }, [useApi, user, saved]);

  const savedPlaces: SavedPlace[] = useApi
    ? savedApi.map((p) => ({ ...p, campus: p.campus as CampusId }))
    : places.filter((p) => saved.includes(p.id)).map((p) => ({ ...p, dishes: [] }));
  const viewSaved = savedPlaces.find((p) => p.id === viewSavedId) ?? null;

  const activeReviews = reviews.filter((r) => r.placeId === active?.id);
  const avg =
    activeReviews.length > 0
      ? activeReviews.reduce((s, r) => s + r.rating, 0) / activeReviews.length
      : 0;

  async function remember(query: string) {
    if (!user) return;
    if (useApi) {
      try {
        await apiPostHistory(campus, budget, radius, query);
        const h = await apiFetchHistory();
        setHistory(
          h.map((x) => ({
            id: x.id,
            campus: x.campus,
            budget: x.budget,
            radiusM: x.radius_m,
            query: x.query,
            createdAt: String(x.created_at),
          })),
        );
      } catch (e) {
        setApiError(e instanceof Error ? e.message : "Lỗi lịch sử");
      }
    } else {
      setHistory(addHistory(user.id, { campus, budget, radiusM: radius, query }));
    }
  }

  function applyIntent(next: Intent) {
    if (next.campus) setCampus(next.campus);
    if (next.budget) setBudget(next.budget);
    if (next.radiusM) setRadius(next.radiusM);
  }

  async function sendChat(text: string) {
  const clean = text.trim();
  if (!clean) return;

  setTurns(t => [
    ...t,
    { role: "user", text: clean }
  ]);

  setDraft("");

  try {
    if (useApi) {
      const result = await postChat(clean, {
        campus: intent.campus,
        budget: intent.budget,
        radius_m: intent.radiusM,
        emotion: emotionCtx,
        emotion_turn: emotionTurn,
        turn_count: turnCount,
      });

      const nextIntent: Intent = {
        campus: result.campus as Intent["campus"],
        budget: result.budget,
        radiusM: result.radius_m,
      };

      setIntent(nextIntent);
      // Persist emotion context for next turn
      setEmotionCtx(result.emotion ?? null);
      setEmotionTurn(result.emotion_turn);
      setTurnCount(result.turn_count ?? turnCount + 1);

      setTurns(t => [
        ...t,
        { role: "bot", text: result.reply }
      ]);

      if (result.ready) {
        applyIntent(nextIntent);
        setTab("list");
        void remember(clean);
      }

    } else {
      // Chế độ offline vẫn sử dụng Regex cũ.
      const result = replyFor(clean, intent);

      setIntent(result.intent);

      setTurns(t => [
        ...t,
        { role: "bot", text: result.say }
      ]);

      if (result.ready) {
        applyIntent(result.intent);
        setTab("list");
      }
    }
  } catch (error) {
    setTurns(t => [
      ...t,
      {
        role: "bot",
        text: "Không thể xử lý yêu cầu. Bạn hãy kiểm tra kết nối backend."
      }
    ]);
  }
}

  function reloadPlaces() {
    if (useApi) {
      void loadFromApi().then(() => {
        setActiveId(null);
        setRegenMsg("Đã tải lại danh sách quán từ MySQL.");
        setTimeout(() => setRegenMsg(""), 3000);
      });
      return;
    }
    const next = generatePlaces();
    setPlaces(next);
    setActiveId(null);
    setRouteCoords([]);
    setRouteMeta(null);
    setRegenMsg(`Đã tạo ${next.length} quán mẫu mới (chế độ offline).`);
    setTimeout(() => setRegenMsg(""), 3000);
  }


  function defaultLatLng(campusId: CampusId, offsetM: number) {
    const o = CAMPUSES[campusId];
    const d = offsetM / 111320;
    const ang = Math.random() * Math.PI * 2;
    return {
      lat: Number((o.lat + d * Math.cos(ang)).toFixed(6)),
      lng: Number((o.lng + d * Math.sin(ang)).toFixed(6)),
    };
  }

  const locMsg = (r: { approx_location: boolean; location_source: string }) =>
    r.location_source === "maps_link"
      ? "Đã lấy vị trí chính xác từ link Google Maps. Quán chỉ hiện trong danh sách nếu nằm trong bán kính đang chọn."
      : r.approx_location
        ? "Vị trí chỉ định vị gần đúng. Hãy kiểm tra bằng link Google Maps hoặc dán link ghim của quán rồi gửi lại."
        : "Đã định vị theo địa chỉ. Quán chỉ hiện trong danh sách nếu nằm trong bán kính đang chọn.";

  async function toggleSavedPlace(placeId: number) {
    if (!user) return;
    if (useApi) {
      try {
        await toggleSaveApi(placeId);
        setSaved(await apiFetchSaves());
      } catch (e) {
        setApiError(e instanceof Error ? e.message : "Lỗi lưu quán");
      }
    } else {
      setSaved(toggleSave(user.id, placeId));
    }
  }

  function clearMenuFiles() {
    setMenuFiles((prev) => {
      prev.forEach((m) => URL.revokeObjectURL(m.url));
      return [];
    });
  }

  async function addMenuFiles(list: File[]) {
    const room = Math.max(0, 10 - menuFiles.length);
    const picked = list.filter((f) => f.type.startsWith("image/")).slice(0, room);
    if (list.length > picked.length) setContribMsg("Tối đa 10 ảnh cho mỗi menu.");
    const shrunk = await Promise.all(picked.map((f) => shrinkImage(f)));
    setMenuFiles((prev) =>
      [...prev, ...shrunk.map((file) => ({ file, url: URL.createObjectURL(file) }))].slice(0, 10),
    );
  }

  function removeMenuFile(i: number) {
    setMenuFiles((prev) => {
      if (prev[i]) URL.revokeObjectURL(prev[i].url);
      return prev.filter((_, j) => j !== i);
    });
  }

  async function runScan() {
    if (menuFiles.length === 0) return;
    setScanBusy(true);
    setContribMsg("");
    try {
      const res = await scanMenuImages(menuFiles.map((m) => m.file));
      const dishes = res.dishes || [];
      setScannedDishes(dishes);
      if (res.restaurant_hint && !contribName.trim()) setContribName(String(res.restaurant_hint));
      if (res.address_hint && !contribAddress.trim()) setContribAddress(String(res.address_hint));
      setScanMeta({
        phone: res.phone ?? "",
        hours: res.hours ?? "",
        notes: (res.notes ?? []).join("\n"),
      });
      setContribMsg(
        `AI đọc được ${dishes.length} món từ ${res.images} ảnh. Kiểm tra rồi bấm Gửi (khoảng giá sẽ tự tính).`,
      );
    } catch (err) {
      setContribMsg(err instanceof Error ? err.message : "Scan menu thất bại");
    } finally {
      setScanBusy(false);
    }
  }

  async function submitContribution(e: React.FormEvent) {
    e.preventDefault();
    if (!user) {
      setContribMsg("Cần đăng nhập để đóng góp quán.");
      setPage("login");
      return;
    }
    const pMin = contribMin.trim() === "" ? undefined : Number(contribMin);
    const pMax = contribMax.trim() === "" ? undefined : Number(contribMax);
    if (pMin !== undefined && pMax !== undefined && pMax < pMin) {
      setContribMsg("Giá max phải ≥ giá min.");
      return;
    }
    setContribBusy(true);
    setContribMsg("");
    const pos = defaultLatLng(campus, contribOffsetM);
    try {
      if (useApi) {
        // Không gửi lat/lng: server tự định vị theo địa chỉ (OpenStreetMap)
        const payload = {
          name: contribName.trim(),
          campus,
          maps_url: contribMapsUrl.trim() || undefined,
          price_min: pMin,
          price_max: pMax,
          cuisine: contribCuisine.trim(),
          address: contribAddress.trim(),
          hours: contribHours.trim(),
          note: contribNote.trim() || undefined,
        };
        if (scannedDishes.length > 0) {
          const res = await contributeWithMenu({
            ...payload,
            dishes: scannedDishes.map((d) => ({
              name: d.name,
              price: d.price,
              category: d.category ?? undefined,
              note: d.note ?? undefined,
              ingredients: (d.ingredients_text ?? "")
                .split(/[,;]/)
                .map((s) => s.trim())
                .filter(Boolean),
            })),
            menu_meta: scanMeta
              ? {
                  phone: scanMeta.phone.trim() || undefined,
                  hours: scanMeta.hours.trim() || undefined,
                  notes: scanMeta.notes.trim() || undefined,
                }
              : undefined,
          });
          setContribMsg(
            `Đã lưu quán #${res.id} + ${res.dishes_saved} món từ menu vào MySQL. ${locMsg(res)}`,
          );
        } else {
          const res = await contributePlace(payload);
          setContribMsg(`Đã lưu MySQL (id=${res.id}). ${locMsg(res)}`);
        }
        setScannedDishes([]);
        clearMenuFiles();
        setScanMeta(null);
        await loadFromApi();
      } else {
        const list = addContribution({
          name: contribName.trim(),
          campus,
          lat: pos.lat,
          lng: pos.lng,
          price_min: pMin ?? 0,
          price_max: pMax ?? pMin ?? 0,
          cuisine: contribCuisine.trim(),
          address: contribAddress.trim(),
          hours: contribHours.trim(),
          note: contribNote.trim() || undefined,
          authorName: user.name,
        });
        setPlaces((prev) => {
          const mapped = list.map((c) => ({
            id: c.id,
            name: c.name,
            campus: c.campus,
            lat: c.lat,
            lng: c.lng,
            price_min: c.price_min,
            price_max: c.price_max,
            cuisine: c.cuisine,
            address: c.address,
            hours: c.hours,
          }));
          const ids = new Set(mapped.map((m) => m.id));
          return [...mapped, ...prev.filter((p) => !ids.has(p.id))];
        });
        setContribMsg("Đã lưu offline (localStorage). Hiện trên list/map.");
      }
      setContribName("");
      setContribNote("");
      setContribMapsUrl("");
      setContribMin("");
      setContribMax("");
      if (!useApi) setTab("list");
    } catch (err) {
      setContribMsg(err instanceof Error ? err.message : "Lỗi gửi đóng góp");
    } finally {
      setContribBusy(false);
    }
  }

  if (page === "login") {

    return (
      <LoginPage
        useApi={useApi}
        onBack={() => setPage("home")}
        onDone={(u) => {
          setUser(u);
          setPage("home");
        }}
      />
    );
  }

  return (
    <div className="app-shell">
      <header className="topbar">
        <div>
          <p className="eyebrow">Sinh viên HCMUS</p>
          <h1 className="title">Ăn gì gần trường</h1>
        </div>
        <div className="row">
          <button type="button" className="chip" title="Tải lại quán" onClick={reloadPlaces}>
            <RefreshCw size={16} style={{ marginRight: 6, verticalAlign: "middle" }} />
            {useApi ? "Tải từ MySQL" : "Tải quán mới"}
          </button>
          {user ? (
            <>
              <span className="muted">{user.name}</span>
              <button
                className="chip"
                type="button"
                onClick={() => {
                  if (useApi) logoutApi();
                  else signOut();
                  setUser(null);
                }}
              >
                Đăng xuất
              </button>
            </>
          ) : (
            <button className="btn-primary" type="button" onClick={() => setPage("login")}>
              Đăng nhập
            </button>
          )}
        </div>
      </header>

      <p className="muted">
        Nguồn dữ liệu:{" "}
        {useApi ? (
          <>
            API + MySQL{" "}
            {mysqlOk === true && <span style={{ color: "#15803d" }}>(DB OK)</span>}
            {mysqlOk === false && <span className="error">(MySQL lỗi — xem CMD uvicorn)</span>}
          </>
        ) : (
          <>offline (localStorage) — tạo file <code>.env</code> với <code>VITE_API_URL=http://localhost:8000</code></>
        )}
      </p>
      {apiError && <p className="error">{apiError}</p>}
      {regenMsg && <p className="muted">{regenMsg}</p>}

      <div className="campus-row">
        {(Object.keys(CAMPUSES) as CampusId[]).map((id) => (
          <button
            key={id}
            type="button"
            className={campus === id ? "chip is-on" : "chip"}
            onClick={() => {
              setCampus(id);
              setActiveId(null);
            }}
          >
            {CAMPUSES[id].short}
          </button>
        ))}
        <a className="chip" href="/hcmus-mysql.sql" download>
          Schema MySQL
        </a>
      </div>

      <section className="filters">
        <label>
          Ngân sách tối đa
          <div className="row wrap">
            {BUDGET_PRESETS.map((n) => (
              <button
                key={n}
                type="button"
                className={budget === n ? "chip is-on" : "chip"}
                onClick={() => setBudget(n)}
              >
                {vnd(n)}
              </button>
            ))}
            <input
              className="field tiny"
              type="number"
              min={10000}
              step={5000}
              value={budget}
              onChange={(e) => setBudget(Number(e.target.value) || 0)}
            />
          </div>
        </label>
        <label>
          Khoảng cách đi bộ
          <div className="row wrap">
            {RADIUS_PRESETS.map((n) => (
              <button
                key={n}
                type="button"
                className={radius === n ? "chip is-on" : "chip"}
                onClick={() => setRadius(n)}
              >
                {n >= 1000 ? `${n / 1000}km` : `${n}m`}
              </button>
            ))}
            <input
              className="field tiny"
              type="number"
              min={100}
              step={100}
              value={radius}
              onChange={(e) => setRadius(Number(e.target.value) || 0)}
            />
          </div>
        </label>
      </section>

      <div className="stage">
        <aside className="panel">
          <div className="tabs">
            {(["list", "chat", "contribute", "me"] as const).map((id) => (
              <button
                key={id}
                type="button"
                className={tab === id ? "tab is-on" : "tab"}
                onClick={() => setTab(id)}
              >
                {id === "list"
                  ? "Quán"
                  : id === "chat"
                    ? "Hỏi trợ lý"
                    : id === "contribute"
                      ? "Đóng góp"
                      : "Của tôi"}
              </button>
            ))}
          </div>

          {tab === "list" && (
            <div className="stack">
              <p className="muted">
                {ranked.length} quán · ≤ {vnd(budget)} · trong {radius}m
              </p>
              {ranked.map((p) => (
                <button
                  key={p.id}
                  type="button"
                  className={active?.id === p.id ? "card is-on" : "card"}
                  onClick={() => setActiveId(p.id)}
                >
                  <strong>{p.name}</strong>
                  <span>
                    {p.cuisine} · {priceText(p)}
                  </span>
                  <span>
                    {p.meters}m · {walkMinutes(p.meters)} phút · {p.hours}
                  </span>
                </button>
              ))}
              {ranked.length === 0 && (
                <p className="muted">Không có quán khớp. Nới lọc hoặc tải lại từ MySQL.</p>
              )}
            </div>
          )}

          {tab === "chat" && (
            <div className="chat">
              <div className="thread">
                {turns.map((t, i) => (
                  <p key={i} className={t.role === "bot" ? "bubble bot" : "bubble me"}>
                    {t.text}
                  </p>
                ))}
              </div>
              <form
                className="composer"
                onSubmit={(e) => {
                  e.preventDefault();
                  sendChat(draft);
                }}
              >
                <input
                  className="field grow"
                  value={draft}
                  placeholder="Quận 5, dưới 35k, 400m"
                  onChange={(e) => setDraft(e.target.value)}
                />
                <button className="btn-primary icon" type="submit" aria-label="Gửi">
                  <Send size={18} />
                </button>
              </form>
            </div>
          )}

          
          {tab === "contribute" && (
            <div className="stack">
              <h2 className="section">Đóng góp quán mới</h2>
              <p className="muted">
                Thêm quán quanh <strong>{CAMPUSES[campus].short}</strong>. Offline lưu máy bạn;
                online (API) lưu MySQL, có chống spam.
              </p>
              {!user && (
                <button className="btn-primary" type="button" onClick={() => setPage("login")}>
                  Đăng nhập để đóng góp
                </button>
              )}
              <form className="stack" onSubmit={(e) => void submitContribution(e)}>
                <label>
                  Tên quán
                  <input className="field" required minLength={2} value={contribName}
                    onChange={(e) => setContribName(e.target.value)} placeholder="Cơm tấm cô Năm" />
                </label>
                <label>
                  Loại món
                  <input className="field" required value={contribCuisine}
                    onChange={(e) => setContribCuisine(e.target.value)} />
                </label>
                <label>
                  Địa chỉ đầy đủ (dùng để định vị trên Google Maps)
                  <textarea className="field" required minLength={4} rows={2} value={contribAddress}
                    onChange={(e) => setContribAddress(e.target.value)}
                    placeholder="VD: 227 Nguyễn Văn Cừ, Phường 4, Quận 5" />
                </label>
                {useApi && (
                  <label>
                    Link Google Maps (tùy chọn, để vị trí chính xác hơn)
                    <input className="field" type="url" value={contribMapsUrl}
                      onChange={(e) => setContribMapsUrl(e.target.value)}
                      placeholder="Mở quán trên Google Maps → Chia sẻ → Sao chép liên kết" />
                  </label>
                )}
                <label>
                  Giờ mở
                  <input className="field" value={contribHours}
                    onChange={(e) => setContribHours(e.target.value)} />
                </label>
                <div className="row wrap">
                  <label>
                    Giá từ (đ) <span className="muted">tùy chọn</span>
                    <input className="field tiny" type="number" min={0} step={1}
                      placeholder="AI tự tính"
                      value={contribMin} onChange={(e) => setContribMin(e.target.value)} />
                  </label>
                  <label>
                    Giá đến (đ) <span className="muted">tùy chọn</span>
                    <input className="field tiny" type="number" min={0} step={1}
                      placeholder="AI tự tính"
                      value={contribMax} onChange={(e) => setContribMax(e.target.value)} />
                  </label>
                </div>
                {!useApi && (
                  <label>
                    Cách cổng ~ (m)
                    <input className="field" type="number" min={50} max={1500} step={50}
                      value={contribOffsetM}
                      onChange={(e) => setContribOffsetM(Number(e.target.value) || 200)} />
                  </label>
                )}
                <label>
                  Ghi chú
                  <input className="field" value={contribNote}
                    onChange={(e) => setContribNote(e.target.value)} placeholder="Món đáng thử…" />
                </label>

                <div className="menu-scan-box">
                  <strong>Ảnh menu (AI đọc món, giá, thông tin quán)</strong>
                  <p className="muted">
                    Menu nhiều trang? Chọn nhiều ảnh một lúc hoặc bấm chọn thêm nhiều lần (tối đa
                    10 ảnh). Cần đăng nhập + API + <code>GEMINI_API_KEY</code>.
                  </p>
                  <input
                    type="file"
                    accept="image/*"
                    multiple
                    disabled={!user || !useApi || scanBusy || menuFiles.length >= 10}
                    onChange={(e) => {
                      const list = Array.from(e.target.files ?? []);
                      e.target.value = "";
                      if (list.length) void addMenuFiles(list);
                    }}
                  />
                  {menuFiles.length > 0 && (
                    <div className="thumbs">
                      {menuFiles.map((m, i) => (
                        <div key={m.url} className="thumb">
                          <img src={m.url} alt={`Trang ${i + 1}`} />
                          <span>Trang {i + 1}</span>
                          <button
                            type="button"
                            className="chip"
                            disabled={scanBusy}
                            onClick={() => removeMenuFile(i)}
                          >
                            Xóa
                          </button>
                        </div>
                      ))}
                    </div>
                  )}
                  {menuFiles.length > 0 && (
                    <button
                      type="button"
                      className="btn-primary"
                      disabled={scanBusy || !user || !useApi}
                      onClick={() => void runScan()}
                    >
                      {scanBusy ? "AI đang đọc menu…" : `AI đọc menu (${menuFiles.length} ảnh)`}
                    </button>
                  )}
                  {scanBusy && (
                    <p className="muted">Đang gửi ảnh cho AI, có thể mất vài chục giây…</p>
                  )}
                  {scanMeta && (
                    <div className="stack">
                      <p className="muted">Thông tin AI đọc được (có thể sửa):</p>
                      <input className="field" placeholder="Số điện thoại" value={scanMeta.phone}
                        onChange={(e) => setScanMeta({ ...scanMeta, phone: e.target.value })} />
                      <input className="field" placeholder="Giờ mở ghi trên menu" value={scanMeta.hours}
                        onChange={(e) => setScanMeta({ ...scanMeta, hours: e.target.value })} />
                      <textarea className="field" rows={2} placeholder="Ghi chú của quán (freeship, phụ thu…)"
                        value={scanMeta.notes}
                        onChange={(e) => setScanMeta({ ...scanMeta, notes: e.target.value })} />
                    </div>
                  )}
                  {scannedDishes.length > 0 && (
                    <div className="dish-list">
                      <p className="muted">
                        Món đã nhận (có thể sửa tên, nhóm, giá). Khoảng giá của quán sẽ tự tính từ
                        các món này.
                      </p>
                      {scannedDishes.map((d, i) => (
                        <div key={i} className="dish-row">
                          <input
                            className="field grow"
                            placeholder="Thành phần (cách nhau bằng dấu phẩy)"
                            value={d.ingredients_text ?? ""}
                            onChange={(e) => {
                              const v = e.target.value;
                              setScannedDishes((prev) =>
                                prev.map((x, j) => (j === i ? { ...x, ingredients_text: v } : x)),
                              );
                            }}
                          />
                          <input
                            className="field tiny"
                            placeholder="Nhóm"
                            value={d.category ?? ""}
                            onChange={(e) => {
                              const v = e.target.value;
                              setScannedDishes((prev) =>
                                prev.map((x, j) => (j === i ? { ...x, category: v || null } : x)),
                              );
                            }}
                          />
                          <input
                            className="field tiny"
                            type="number"
                            min={0}
                            placeholder="Giá"
                            value={d.price ?? ""}
                            onChange={(e) => {
                              const v = e.target.value === "" ? null : Number(e.target.value);
                              setScannedDishes((prev) =>
                                prev.map((x, j) => (j === i ? { ...x, price: v } : x)),
                              );
                            }}
                          />
                          <button
                            type="button"
                            className="chip"
                            onClick={() =>
                              setScannedDishes((prev) => prev.filter((_, j) => j !== i))
                            }
                          >
                            Xóa
                          </button>
                        </div>
                      ))}
                      <button
                        type="button"
                        className="chip"
                        onClick={() =>
                          setScannedDishes((prev) => [...prev, { name: "Món mới", price: null }])
                        }
                      >
                        + Thêm món
                      </button>
                    </div>
                  )}
                </div>

                {contribMsg && (
                  <p className={
                    /lỗi|loi|cần|nhanh|vượt|trùng|tải cao|phải|không|khong|thất bại/i.test(contribMsg) ? "error" : "muted"
                  }>{contribMsg}</p>
                )}
                <button className="btn-primary" type="submit" disabled={contribBusy || !user}>
                  {contribBusy ? "Đang gửi…" : "Gửi đóng góp"}
                </button>
              </form>
            </div>
          )}

{tab === "me" && (
            <div className="stack">
              {!user && (
                <>
                  <p className="muted">
                    Đăng nhập để lưu quán và lịch sử
                    {useApi ? " trên MySQL." : " (localStorage)."}
                  </p>
                  <button className="btn-primary" type="button" onClick={() => setPage("login")}>
                    Đăng nhập / đăng ký
                  </button>
                </>
              )}
              {user && (
                <>
                  <button
                    type="button"
                    className={onlySaved ? "chip is-on" : "chip"}
                    onClick={() => setOnlySaved((v) => !v)}
                  >
                    {onlySaved ? "Đang xem quán đã lưu" : "Chỉ hiện quán đã lưu"}
                  </button>
                  <h2 className="section">Quán đã lưu ({savedPlaces.length})</h2>
                  {savedPlaces.length === 0 && (
                    <p className="muted">Chưa lưu quán nào. Mở một quán và bấm biểu tượng dấu trang.</p>
                  )}
                  {viewSaved ? (
                    <SavedPlaceDetail
                      place={viewSaved}
                      onBack={() => setViewSavedId(null)}
                      onUnsave={async () => {
                        if (!window.confirm(`Bỏ lưu "${viewSaved.name}"?`)) return;
                        await toggleSavedPlace(viewSaved.id);
                        setViewSavedId(null);
                      }}
                    />
                  ) : (
                    savedPlaces.map((p) => (
                      <button
                        key={p.id}
                        type="button"
                        className="card"
                        onClick={() => setViewSavedId(p.id)}
                      >
                        <strong>{p.name}</strong>
                        <span>
                          {p.cuisine} · {priceText(p)}
                        </span>
                        <span>{splitAddress(p.address).address}</span>
                      </button>
                    ))
                  )}
                  <h2 className="section">Lịch sử</h2>
                  {history.length === 0 && <p className="muted">Chưa có lịch sử.</p>}
                  {history.map((h) => (
                    <button
                      key={h.id}
                      type="button"
                      className="card"
                      onClick={() => {
                        setCampus(h.campus as CampusId);
                        setBudget(h.budget);
                        setRadius(h.radiusM);
                        setTab("list");
                      }}
                    >
                      <strong>{h.query}</strong>
                      <span>
                        {h.campus === "q5" ? "Quận 5" : "Làng ĐH"} · {vnd(h.budget)} · {h.radiusM}m
                      </span>
                    </button>
                  ))}
                  <button
                    type="button"
                    className="chip"
                    onClick={() =>
                      void remember(`Thủ công ${CAMPUSES[campus].short} ${budget} ${radius}m`)
                    }
                  >
                    Lưu lần tìm hiện tại
                  </button>
                </>
              )}
            </div>
          )}

          {active && tab === "list" && (
            <div className="detail">
              <div className="row between">
                <h2 className="section">{active.name}</h2>
                {user && (
                  <button
                    type="button"
                    className="icon-btn"
                    aria-label="Lưu quán"
                    onClick={() => void toggleSavedPlace(active.id)}
                  >
                    <Bookmark size={18} fill={saved.includes(active.id) ? "currentColor" : "none"} />
                  </button>
                )}
              </div>
              <div className="route-box">
                <strong>Chỉ đường trên bản đồ</strong>
                {routeLoading && <p className="muted">Đang tính đường đi bộ…</p>}
                {!routeLoading && routeMeta && (
                  <p className="muted">
                    Đi bộ khoảng <strong>{routeMeta.distanceM} m</strong> ·{" "}
                    <strong>{Math.max(1, Math.round(routeMeta.durationSec / 60))} phút</strong>
                  </p>
                )}
                {routeError && <p className="error">{routeError}</p>}
              </div>
              <a
                className="chip"
                target="_blank"
                rel="noreferrer"
                href={`https://www.google.com/maps/dir/?api=1&origin=${CAMPUSES[campus].lat},${CAMPUSES[campus].lng}&destination=${active.lat},${active.lng}&travelmode=walking`}
              >
                Chỉ đường Google Maps (tab mới)
              </a>{" "}
              <a className="chip" target="_blank" rel="noreferrer" href={mapsSearchUrl(active.address)}>
                Xem địa chỉ trên Google Maps
              </a>{" "}
              <a className="chip" target="_blank" rel="noreferrer" href={mapsPinUrl(active.lat, active.lng)}>
                Xem theo vị trí đã định vị
              </a>
              <PlaceInfoText place={active} info={activeInfo} />
              <p className="muted">
                Đánh giá:{" "}
                {activeReviews.length ? `${avg.toFixed(1)}/5 · ${activeReviews.length}` : "chưa có"}
              </p>
              {activeReviews.slice(0, 3).map((r) => (
                <p key={r.id} className="review">
                  <strong>{r.authorName}</strong> · {r.rating}/5 — {r.body}
                </p>
              ))}
              {user && (
                <form
                  className="stack"
                  onSubmit={async (e) => {
                    e.preventDefault();
                    if (useApi) {
                      try {
                        await apiPostReview(active.id, stars, note.trim());
                        const revs = await apiFetchReviews();
                        setReviews(
                          revs.map((r) => ({
                            id: r.id,
                            placeId: r.place_id,
                            authorName: r.author_name,
                            rating: r.rating,
                            body: r.body,
                            createdAt: String(r.created_at),
                          })),
                        );
                        setNote("");
                      } catch (err) {
                        setApiError(err instanceof Error ? err.message : "Lỗi đánh giá");
                      }
                    } else {
                      setReviews(
                        addReview({
                          placeId: active.id,
                          authorName: user.name,
                          rating: stars,
                          body: note.trim(),
                        }),
                      );
                      setNote("");
                    }
                  }}
                >
                  <div className="row">
                    {[1, 2, 3, 4, 5].map((n) => (
                      <button
                        key={n}
                        type="button"
                        className={stars === n ? "chip is-on" : "chip"}
                        onClick={() => setStars(n)}
                      >
                        {n}
                      </button>
                    ))}
                  </div>
                  <input
                    className="field"
                    value={note}
                    placeholder="Món nào đáng tiền?"
                    onChange={(e) => setNote(e.target.value)}
                    required
                    minLength={4}
                  />
                  <button className="btn-primary" type="submit">
                    Gửi đánh giá
                  </button>
                </form>
              )}
            </div>
          )}
        </aside>

        <div className="map-wrap">
          <CampusMap
            campus={campus}
            places={ranked}
            activeId={active?.id ?? null}
            routeCoords={routeCoords}
            onPick={setActiveId}
          />
          <p className="map-note">
            {useApi
              ? "Quán lấy từ MySQL qua API Python. Chỉ đường OSRM trên map."
              : "Offline: quán mẫu trong JS. Bật MySQL + VITE_API_URL để dùng database."}
          </p>
        </div>
      </div>
    </div>
  );
}

function LoginPage({
  useApi,
  onBack,
  onDone,
}: {
  useApi: boolean;
  onBack: () => void;
  onDone: (u: User) => void;
}) {
  const [mode, setMode] = useState<"in" | "up">("in");
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setBusy(true);
    try {
      if (useApi) {
        const data =
          mode === "up"
            ? await apiSignup(email, password, name)
            : await apiLogin(email, password);
        onDone(data.user);
      } else {
        const res = mode === "up" ? signUp(email, password, name) : signIn(email, password);
        if (!res.ok) setError(res.error);
        else onDone(res.user);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Lỗi đăng nhập");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="login-page">
      <div className="login-card">
        <button type="button" className="chip" onClick={onBack}>
          ← Về bản đồ
        </button>
        <h1 className="title">HCMUS Ăn Gì</h1>
        <p className="muted">
          {useApi
            ? "Tài khoản lưu trên MySQL qua API Python."
            : "Chế độ offline — tài khoản chỉ trên trình duyệt này."}
        </p>
        <form className="stack" onSubmit={submit}>
          {mode === "up" && (
            <input
              className="field"
              placeholder="Tên hiển thị"
              value={name}
              onChange={(e) => setName(e.target.value)}
              required
            />
          )}
          <input
            className="field"
            type="email"
            placeholder="Email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
          />
          <input
            className="field"
            type="password"
            placeholder="Mật khẩu"
            minLength={6}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
          />
          {error && <p className="error">{error}</p>}
          <button className="btn-primary" type="submit" disabled={busy}>
            {busy ? "Đang xử lý…" : mode === "up" ? "Tạo tài khoản" : "Đăng nhập"}
          </button>
          <button type="button" className="chip" onClick={() => setMode(mode === "up" ? "in" : "up")}>
            {mode === "up" ? "Đã có tài khoản? Đăng nhập" : "Chưa có? Đăng ký"}
          </button>
        </form>
      </div>
    </main>
  );
}

function priceText(p: { price_min: number; price_max: number }) {
  if (!(p.price_max > 0)) return "Chưa rõ giá";
  return p.price_min === p.price_max ? vnd(p.price_min) : `${vnd(p.price_min)}–${vnd(p.price_max)}`;
}

/** Gom món theo nhóm (giữ thứ tự xuất hiện). Món không nhóm → "Khác" nếu quán có nhóm khác. */
function groupDishes(dishes: ApiDish[]): [string, ApiDish[]][] {
  const hasCats = dishes.some((d) => d.category);
  const map = new Map<string, ApiDish[]>();
  for (const d of dishes) {
    const k = d.category || (hasCats ? "Khác" : "");
    map.set(k, [...(map.get(k) ?? []), d]);
  }
  return [...map.entries()];
}

function buildInfoText(place: Place, info: ApiPlaceInfo): string {
  const { address, note } = splitAddress(place.address);
  const m = info.menu_meta;
  const lines = [
    place.name,
    `Loại món: ${place.cuisine}`,
    `Khoảng giá: ${priceText(place)}`,
    `Giờ mở: ${place.hours || "Chưa rõ"}`,
    `Địa chỉ: ${address}`,
  ];
  if (note) lines.push(`Ghi chú: ${note}`);
  if (m?.phone) lines.push(`SĐT: ${m.phone}`);
  if (m?.hours && m.hours !== place.hours) lines.push(`Giờ ghi trên menu: ${m.hours}`);
  if (m?.notes) lines.push(`Lưu ý của quán: ${m.notes.replace(/\n+/g, "; ")}`);
  if (info.dishes.length) {
    lines.push("", `MENU (${info.dishes.length} món)`);
    for (const [cat, items] of groupDishes(info.dishes)) {
      if (cat) lines.push(`# ${cat}`);
      for (const d of items) {
        lines.push(
          `- ${d.name}${d.note ? ` (${d.note})` : ""}: ${d.price != null ? vnd(d.price) : "chưa rõ giá"}`,
        );
      }
    }
  }
  return lines.join("\n");
}

function MenuBlock({ dishes }: { dishes: ApiDish[] }) {
  const [openId, setOpenId] = useState<number | null>(null);
  if (dishes.length === 0) return <p className="muted">Chưa có menu cho quán này.</p>;
  return (
    <div className="menu-text">
      <strong>Menu ({dishes.length} món) · bấm vào món để xem thành phần</strong>
      {groupDishes(dishes).map(([cat, items]) => (
        <div key={cat || "_"} className="menu-group">
          {cat && <em className="menu-cat">{cat}</em>}
          <ul>
            {items.map((d) => {
              const open = openId === d.id;
              const ings = d.ingredients ?? [];
              return (
                <li key={d.id}>
                  <button
                    type="button"
                    className="dish-btn"
                    aria-expanded={open}
                    onClick={() => setOpenId(open ? null : d.id)}
                  >
                    <span>
                      {d.name}
                      {d.note ? ` (${d.note})` : ""}
                    </span>
                    <span>{d.price != null ? vnd(d.price) : "—"}</span>
                  </button>
                  {open && (
                    <div className="dish-ings">
                      <strong>Thành phần</strong>
                      {ings.length ? (
                        <div className="ing-tags">
                          {ings.map((x) => (
                            <span key={x} className="ing-tag">{x}</span>
                          ))}
                        </div>
                      ) : (
                        <p className="muted">Chưa có thông tin thành phần.</p>
                      )}
                      <p className="muted">
                        Do người đóng góp nhập, chỉ để tham khảo. Nếu dị ứng nặng, hãy hỏi lại quán.
                      </p>
                    </div>
                  )}
                </li>
              );
            })}
          </ul>
        </div>
      ))}
    </div>
  );
}

/** Thông tin quán dạng text: loại món, giá, giờ, địa chỉ, SĐT, ghi chú, menu theo nhóm. */
function PlaceInfoText({ place, info }: { place: Place; info: ApiPlaceInfo }) {
  const { address, note } = splitAddress(place.address);
  const m = info.menu_meta;
  const [copied, setCopied] = useState(false);
  return (
    <div className="info-text">
      <strong>Thông tin quán</strong>
      <dl>
        <dt>Loại món</dt>
        <dd>{place.cuisine}</dd>
        <dt>Khoảng giá</dt>
        <dd>{priceText(place)}</dd>
        <dt>Giờ mở</dt>
        <dd>{place.hours || "Chưa rõ"}</dd>
        {m?.hours && m.hours !== place.hours && (
          <>
            <dt>Giờ ghi trên menu</dt>
            <dd>{m.hours}</dd>
          </>
        )}
        <dt>Địa chỉ</dt>
        <dd>{address}</dd>
        {note && (
          <>
            <dt>Ghi chú</dt>
            <dd>{note}</dd>
          </>
        )}
        {m?.phone && (
          <>
            <dt>SĐT</dt>
            <dd>
              <a href={`tel:${m.phone.replace(/[^\d+]/g, "")}`}>{m.phone}</a>
            </dd>
          </>
        )}
        {m?.notes && (
          <>
            <dt>Lưu ý của quán</dt>
            <dd style={{ whiteSpace: "pre-line" }}>{m.notes}</dd>
          </>
        )}
      </dl>
      <MenuBlock dishes={info.dishes} />
      <button
        type="button"
        className="chip"
        onClick={async () => {
          try {
            await navigator.clipboard.writeText(buildInfoText(place, info));
            setCopied(true);
            setTimeout(() => setCopied(false), 2000);
          } catch {
            /* trình duyệt chặn clipboard */
          }
        }}
      >
        {copied ? "Đã sao chép" : "Sao chép thông tin (text)"}
      </button>
    </div>
  );
}

function SavedPlaceDetail({
  place,
  onBack,
  onUnsave,
}: {
  place: SavedPlace;
  onBack: () => void;
  onUnsave: () => void;
}) {
  return (
    <div className="detail">
      <button type="button" className="chip" onClick={onBack}>
        ← Danh sách đã lưu
      </button>
      <h2 className="section">{place.name}</h2>
      <div className="row wrap">
        <a className="chip" target="_blank" rel="noreferrer" href={mapsSearchUrl(place.address)}>
          Xem địa chỉ trên Google Maps
        </a>
        <a className="chip" target="_blank" rel="noreferrer" href={mapsPinUrl(place.lat, place.lng)}>
          Xem theo vị trí đã định vị
        </a>
        <button type="button" className="chip" onClick={onUnsave}>
          Bỏ lưu quán
        </button>
      </div>
      <PlaceInfoText place={place} info={{ dishes: place.dishes, menu_meta: place.menu_meta ?? null }} />
    </div>
  );
}
