import { useCallback, useEffect, useMemo,useRef, useState } from "react";
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
import { useUserLocation } from "./lib/useUserLocation";

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
  saveSurveyApi,
  fetchPreferenceApi,
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
  DEFAULT_PREFERENCE,
  type SurveyAnswers,
  type SurveyChoice,
  type SurveyFactor,
  type UserPreference,
} from "./lib/heana-types";
import { FACTOR_LABEL, preferenceFromChoices } from "./lib/heana-ranking";
//random-suggest-test
import { suggestRandomPlaces } from "./lib/random-suggest";

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
  getGuestPref,
  setGuestPref,
  isSurveySkipped,
  setSurveySkipped,
  type HistoryItem,
  type Review,
  type User,
} from "./lib/storage";
import { CampusMap } from "./components/CampusMap";
import { ChatHome, type NavTarget } from "./components/ChatHome";
import { PlacePage, type PlaceMode } from "./components/PlacePage";

// import { PlaceListView } from "./components/PlaceListView";

import { fbAuth } from "./lib/firebase";
import {
  createUserWithEmailAndPassword,
  signInWithEmailAndPassword,
  sendEmailVerification,
  updateProfile,
} from "firebase/auth";
import { loginWithFirebaseToken } from "./lib/api";

import { onAuthStateChanged } from "firebase/auth";

type SavedPlace = Place & { dishes: ApiDish[]; menu_meta?: ApiMenuMeta | null };
type MenuFile = { file: File; url: string };
type ScanMeta = { phone: string; hours: string; notes: string };
type SortKey = "near" | "price_asc" | "price_desc";

/** Bỏ dấu tiếng Việt + chữ thường để so khớp tìm kiếm ("pho" khớp "Phở"). */
function normalizeText(s: string) {
  return s
    .toLowerCase()
    .replace(/đ/g, "d")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .trim();
}

export default function App() {
    const [suggestedIds, setSuggestedIds] = useState<number[]>([]);
  const useApi = apiEnabled();
  const [mysqlOk, setMysqlOk] = useState<boolean | null>(null);
  const [apiError, setApiError] = useState("");
  const [user, setUser] = useState<User | null>(null);
  const [places, setPlaces] = useState<Place[]>(() => initialPlaces());
  const [reviews, setReviews] = useState<Review[]>([]);
  const [saved, setSaved] = useState<number[]>([]);
  const [history, setHistory] = useState<HistoryItem[]>([]);
  const [campus, setCampus] = useState<CampusId>("q5");
  const userLoc = useUserLocation(campus);
  const [budget, setBudget] = useState<number | null>(null);
  const [radius, setRadius] = useState<number | null>(null);
  const [onlySaved, setOnlySaved] = useState(false);
  const [query, setQuery] = useState("");
  const [directoryQuery, setDirectoryQuery] = useState("");
  const [directoryHistoryFilter, setDirectoryHistoryFilter] = useState(false);
  const [namedSearch, setNamedSearch] = useState<{ acrossCampuses: boolean } | null>(null);
  const [sortBy, setSortBy] = useState<SortKey>("near");
  const [activeId, setActiveId] = useState<number | null>(null);
  const [tab, setTab] = useState<"list" | "chat" | "me" | "contribute">("list");
  const [intent, setIntent] = useState<Intent>({});
  const [chatFilter, setChatFilter] = useState({ food: "", place: "" });
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
  // "chat" = giao diện chat mới (mặc định); "classic" = giao diện danh sách + bản đồ cũ
  const [screen, setScreen] = useState<"chat" | "classic" | "place">("chat");
  const [placeMode, setPlaceMode] = useState<PlaceMode>("detail");
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

  const [pref, setPref] = useState<UserPreference>(DEFAULT_PREFERENCE);
  const [surveyStage, setSurveyStage] = useState<"q1" | "q2" | "q3" | null>(null);
  const [surveyAns, setSurveyAns] = useState<{ q1: SurveyChoice; q2: SurveyChoice | null }>({
    q1: "any",
    q2: null,
  });
  const askedFor = useRef<string | null>(null);
  // true = khảo sát này được bật từ nút 🎲 -> làm xong sẽ tự động random
  const pendingRandom = useRef(false);

  const loadFromApi = useCallback(async () => {
    if (!useApi) return;
    setApiError("");
    try {
      const h = await apiHealth();
      setMysqlOk(h.mysql);
      const list = await apiFetchPlaces(campus);
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
          image_url: (p as { image_url?: string | null }).image_url ?? null,
          dish_names: p.dish_names ?? [],
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
  }, [useApi, campus]);

  useEffect(() => {
  if (!useApi) return;

  async function syncVerification() {
    const u = fbAuth.currentUser;
    if (!u) return;
    await u.reload();                       // lấy trạng thái mới nhất từ Firebase
    if (!u.emailVerified) return;
    const stored = getApiUser() as { email_verified?: boolean } | null;
    if (stored?.email_verified) return;     // đã đồng bộ rồi, khỏi gọi lại
    const data = await loginWithFirebaseToken(await u.getIdToken(true));
    setUser(data.user);                     // JWT mới có ev = true, DB cập nhật = 1
  }

  const run = () => { void syncVerification().catch(() => {}); };
  const unsub = onAuthStateChanged(fbAuth, run);   // khi mở lại trang
  window.addEventListener("focus", run);           // khi quay lại từ tab email
  return () => {
    unsub();
    window.removeEventListener("focus", run);
  };
}, [useApi]);

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

  const browsingDirectory = screen === "classic" && tab === "list";
  const searchText = browsingDirectory ? directoryQuery : query;
  const ranked = useMemo(() => {
    const tokens = normalizeText(searchText).split(/\s+/).filter(Boolean);
    const allCampuses = browsingDirectory ? !directoryHistoryFilter : Boolean(chatFilter.place) && !intent.campus;
    const limitResults = browsingDirectory ? directoryHistoryFilter : true;

    const food = browsingDirectory ? "" : normalizeText(chatFilter.food);
    const placeQ = browsingDirectory ? "" : normalizeText(chatFilter.place);

    // 3 = tên quán chứa món, 2 = có món trong menu, 1 = loại món khớp, 0 = không liên quan
    const relevance = (p: Place) => {
      if (!food) return 0;
      if  (normalizeText(p.name).includes(food)) return 3;
      if ((p.dish_names ?? []).some((d) => normalizeText(d).includes(food))) return 2;
      if (normalizeText(p.cuisine).includes(food)) return 1;
      return 0;
    };

    const list = places
      .filter((p) => allCampuses || p.campus === campus)
      .map((p) => ({
        ...p,
        meters: Math.round(haversine(CAMPUSES[p.campus].lat, CAMPUSES[p.campus].lng, p.lat, p.lng)),
      }))
      .filter((p) => !limitResults || ((budget === null || p.price_min <= budget * 1.1) && (radius === null || p.meters <= radius * 1.2)))
      .filter((p) => !onlySaved || saved.includes(p.id))
      .filter((p) => {
        if (browsingDirectory) {
          if (!tokens.length) return true;
          const hay = normalizeText(`${p.name} ${p.cuisine} ${p.address}`);
          return tokens.every((t) => hay.includes(t));
        }
        if (placeQ && !normalizeText(p.name).includes(placeQ)) return false;
        if (food && relevance(p) === 0) return false; // loại hẳn quán không liên quan
        return true;
      });

    const priceKnown = (p: { price_max: number }) => p.price_max > 0;
    list.sort((a, b) => {
      if (food) {
        const d = relevance(b) - relevance(a);
        if (d) return d;
      }
      if (sortBy === "near") return a.meters - b.meters;
      if (priceKnown(a) !== priceKnown(b)) return priceKnown(a) ? -1 : 1;
      const diff = sortBy === "price_asc" ? a.price_min - b.price_min : b.price_max - a.price_max;
      return diff || a.meters - b.meters;
    });
    return list;
  }, [places, campus, budget, radius, onlySaved, saved, searchText, sortBy,
      browsingDirectory, directoryHistoryFilter, chatFilter, intent.campus]);

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
    const origin = userLoc.origin;
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
  }, [active?.id, campus, active?.lat, active?.lng, userLoc.origin.lat, userLoc.origin.lng]);

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

 
  useEffect(() => {
    let cancelled = false;
    const key = user?.id ?? "guest";
    const autoAsk = () => {
      if (askedFor.current === key) return;
      if (isSurveySkipped(key)) return
      askedFor.current = key;
      startSurvey(true);
    };
    (async () => {
      if (user && useApi) {
        try {
          const p = await fetchPreferenceApi();
          if (cancelled) return;
          setPref(p);
          if (!p.survey_done) autoAsk();
        } catch { /* token hết hạn */ }
      } else {
        const g = getGuestPref();
        setPref(g ?? DEFAULT_PREFERENCE);
        if (!g) autoAsk();
      }
    })();
    return () => { cancelled = true; };
  }, [user, useApi]);

  const savedPlaces: SavedPlace[] = useApi
    ? savedApi.map((p) => ({ ...p, campus: p.campus as CampusId }))
    : places.filter((p) => saved.includes(p.id)).map((p) => ({ ...p, dishes: [] }));
  const viewSaved = savedPlaces.find((p) => p.id === viewSavedId) ?? null;

  const activeReviews = reviews.filter((r) => r.placeId === active?.id);
  const avg =
    activeReviews.length > 0
      ? activeReviews.reduce((s, r) => s + r.rating, 0) / activeReviews.length
      : 0;

  const ratings = useMemo(() => {
    const m: Record<number, { avg: number; count: number }> = {};
    for (const r of reviews) {
      const cur = m[r.placeId] ?? { avg: 0, count: 0 };
      m[r.placeId] = { avg: (cur.avg * cur.count + r.rating) / (cur.count + 1), count: cur.count + 1 };
    }
    return m;
  }, [reviews]);

  async function remember(query: string, search = { campus, budget, radiusM: radius }) {
    if (!user) return;
    if (useApi) {
      try {
        await apiPostHistory(search.campus, search.budget, search.radiusM, query);
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
      setHistory(addHistory(user.id, { ...search, query }));
    }
  }

  function applyIntent(next: Intent) {
    if (next.campus) setCampus(next.campus);
    if (next.budget !== undefined) setBudget(next.budget);
    if (next.radiusM !== undefined) setRadius(next.radiusM);
  }
    //recommend random 
    // opts.pref: dùng khảo sát vừa làm xong (state `pref` chưa kịp cập nhật trong cùng lượt render)
    // opts.reset: khảo sát mới -> cho phép bốc lại cả những quán đã gợi ý trước đó
    // opts.echo === false: không thêm bong bóng "user" (đã thêm lúc bắt đầu khảo sát)
    function suggestRandom(opts?: { pref?: UserPreference; reset?: boolean; echo?: boolean }) {
        if (opts?.echo !== false) {
            setTurns((t) => [...t, { role: "user", text: "🎲 Gợi ý cho mình 5 quán" }]);
        }
        const picks = suggestRandomPlaces(
            ranked, ratings, opts?.pref ?? pref, CAMPUSES[campus], radius ?? ranked.reduce((max, p) => Math.max(max, p.meters), 1),
            opts?.reset ? [] : suggestedIds, 5,
        );
        if (!picks.length) {
            setTurns((t) => [...t, {
                role: "bot",
                text: "Chưa có quán nào khớp ngân sách và bán kính hiện tại. Bạn thử tăng ngân sách hoặc khoảng cách nhé."
            }]);
            return;
        }
        const ids = picks.map((s) => s.place.id);
        setSuggestedIds((prev) => [...new Set([...(opts?.reset ? [] : prev), ...ids])]);
        setActiveId(ids[0]);
        setTurns((t) => [...t, {
            role: "bot",
            text: picks.length < 5
                ? `Hiện chỉ có ${picks.length} quán khớp ngân sách và bán kính, mình gợi ý hết cho bạn nhé! Bấm vào từng quán để xem chi tiết hoặc chỉ đường.`
                : "Mình bốc ngẫu nhiên 5 quán hợp với ưu tiên của bạn nhé! Bấm vào từng quán để xem chi tiết hoặc chỉ đường.",
            list: true,
            picks: ids,
        }]);
    }

  /** Nút 🎲 chính: làm khảo sát trước, xong mới random dựa trên khảo sát mới. */
  function startRandomFlow() {
    setTurns((t) => [...t, { role: "user", text: "🎲 Gợi ý cho mình 5 quán" }]);
    startSurvey(
      false,
      "Trước khi bốc quán, bạn trả lời nhanh bài khảo sát này để mình gợi ý đúng ý bạn nhất nhé!\n\n",
    );
    pendingRandom.current = true; // đặt SAU startSurvey (startSurvey sẽ reset cờ này)
  }
  function startNewChat() {
    setTurns((t) => t.slice(0, 1));
    setDraft("");
    setIntent({});
    setEmotionCtx(null);
    setEmotionTurn(undefined);
    setTurnCount(0);
    pendingRandom.current = false;
    setSurveyStage(null);
    setSurveyAns({ q1: "any", q2: null });
    setSuggestedIds([]);
    setQuery("");
    setCampus("q5");
    setBudget(null);
    setRadius(null);
    setOnlySaved(false);
    setSortBy("near");
    setActiveId(null);
    setChatFilter({ food: "", place: "" });
  }
  async function sendChat(text: string) {
  const clean = text.trim();
  if (!clean) return;

  if (surveyStage === "q3") {
    void finishSurvey(clean);
    return;
  }
  if (surveyStage === "q1" || surveyStage === "q2") {
    setDraft("");
    setTurns((t) => [
      ...t,
      { role: "user", text: clean },
      {
        role: "bot",
        text: 'Bạn bấm một lựa chọn bên trên nhé (hoặc "Bỏ qua lúc này").',
        // gắn lại nút vì ChatHome chỉ hiện nút ở bong bóng cuối cùng
        choices: surveyStage === "q1" ? q1Choices() : q2Choices(surveyAns.q1),
      },
    ]);
    return;
  }

  setTurns(t => [
    ...t,
    { role: "user", text: clean }
  ]);

  setDraft("");

  try {
    if (useApi) {
      const result = await postChat(clean, {
        budget_unlimited: intent.budget === null,
        radius_unlimited: intent.radiusM === null,
        budget_is_default: intent.budgetIsDefault,
        radius_is_default: intent.radiusIsDefault,
        food_name: intent.foodName,
        place_name: intent.placeName,
        campus: intent.campus,
        budget: intent.budget,
        radius_m: intent.radiusM,
        emotion: emotionCtx,
        emotion_turn: emotionTurn,
        turn_count: turnCount,
      });

      const nextIntent: Intent = {
        campus: result.campus as Intent["campus"],
        budget: result.budget_unlimited ? null : result.budget ?? undefined,
        radiusM: result.radius_unlimited ? null : result.radius_m ?? undefined,
        foodName: result.food_name,
        placeName: result.place_name,
      };

      setIntent(nextIntent);
      setChatFilter({food: result.food_name ?? "", place: result.place_name ?? ""});
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
        setTurns(t => [...t, { role: "bot", text: "Danh sách quán", list: true }]);
        setActiveId(null);
        void remember(clean, { campus: nextIntent.campus ?? campus, budget: nextIntent.budget ?? null, radiusM: nextIntent.radiusM ?? null });
      }

    } else {
      // Chế độ offline vẫn sử dụng Regex cũ.
      const result = replyFor(clean, intent);

      setIntent(result.intent);
      setChatFilter({food: result.intent.foodName ?? "", place: result.intent.placeName ?? ""});

      setTurns(t => [
        ...t,
        { role: "bot", text: result.say }
      ]);

      if (result.ready) {
        applyIntent(result.intent);
        setTurns(t => [...t, { role: "bot", text: "Danh sách quán", list: true }]);
        setActiveId(null);
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
        setRegenMsg("Đã tải lại danh sách quán.");
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
        `Đã đọc được ${dishes.length} món từ ${res.images} ảnh. Kiểm tra rồi bấm Gửi (khoảng giá sẽ tự tính).`,
      );
    } catch (err) {
      setContribMsg(err instanceof Error ? err.message : "Scan menu thất bại");
    } finally {
      setScanBusy(false);
    }
  }

  async function submitSurvey(a: SurveyAnswers): Promise<UserPreference> {
    let p: UserPreference;
    if (user && useApi) {
      p = await saveSurveyApi(a);                     // server tính + lưu MySQL
    } else {
      p = preferenceFromChoices(a);                   // khách: không gọi API
      setGuestPref(p);
    }
    setPref(p);
    return p;
  }

  const NAV = {
    back: { label: "← Đổi câu trước", value: "__back" },
    skip: { label: "Bỏ qua lúc này", value: "__skip" },
  };

  const ASK_ALLERGY =
    'Câu 3: Cảm ơn bạn! Bạn có thành phần nào khiến bạn dị ứng hoặc khó chịu khi ăn không? Gõ vào ô chat bên dưới (cách nhau bằng dấu phẩy), hoặc gõ "không" nếu không có.';

  const q1Choices = () => [
    { label: FACTOR_LABEL.price, value: "price" },
    { label: FACTOR_LABEL.distance, value: "distance" },
    { label: FACTOR_LABEL.quality, value: "quality" },
    { label: "Sao cũng được", value: "any" },
    NAV.skip,
  ];

  const q2Choices = (q1: SurveyChoice) => [
    ...(["price", "distance", "quality"] as SurveyFactor[])
      .filter((f) => f !== q1)
      .map((f) => ({ label: FACTOR_LABEL[f], value: f })),
    { label: "Sao cũng được", value: "any" },
    NAV.back,
    NAV.skip,
  ];

  const q1Turn = (intro = ""): ChatTurn => ({
    role: "bot",
    text: `${intro}Câu 1: Bạn muốn kết quả tìm kiếm ưu tiên yếu tố nào nhất?`,
    choices: q1Choices(),
  });
  const q2Turn = (q1: SurveyChoice): ChatTurn => ({
    role: "bot",
    text: "Câu 2: Hãy chọn yếu tố phụ để mình đưa ra lựa chọn tốt hơn cho bạn",
    choices: q2Choices(q1),
  });
  const q3Turn = (): ChatTurn => ({
    role: "bot",
    text: ASK_ALLERGY,
    choices: [NAV.back, NAV.skip],
  });

  function startSurvey(first: boolean, customIntro?: string) {
    pendingRandom.current = false; // khảo sát mở từ menu / lần đầu thì không tự random
    setSurveyStage("q1");
    setSurveyAns({ q1: "any", q2: null });
    setScreen("chat");
    const intro =
      customIntro ??
      (first
        ? "Chào bạn mới! Trước khi chúng ta bắt đầu việc lựa chọn quán, bạn hãy thực hiện bài khảo sát này để giúp mình tìm quán phù hợp với bạn nhất! (Bạn có thể thực hiện lại bất kỳ lúc nào bạn muốn)\n\n"
        : "");
    setTurns((t) => [...t, q1Turn(intro)]);
  }

  function goBack(label: string) {
    const echo: ChatTurn = { role: "user", text: label };
    if (surveyStage === "q3" && surveyAns.q1 !== "any") {
      setSurveyStage("q2");
      setSurveyAns((a) => ({ ...a, q2: null }));
      setTurns((t) => [...t, echo, q2Turn(surveyAns.q1)]);
    } else if (surveyStage === "q3" || surveyStage === "q2") {
      setSurveyStage("q1");
      setSurveyAns({ q1: "any", q2: null });
      setTurns((t) => [...t, echo, q1Turn()]);
    }
  }

  function skipSurvey(label: string) {
    setSurveyStage(null);
    setSurveyAns({ q1: "any", q2: null });
    setSurveySkipped(user?.id ?? "guest"); // tải lại trang không hỏi lại
    setTurns((t) => [...t, { role: "user", text: label }]);
    if (pendingRandom.current) {
      pendingRandom.current = false;
      setTurns((t) => [...t, { role: "bot", text: "Ok, mình bốc quán theo ưu tiên hiện tại nhé." }]);
      suggestRandom({ pref, reset: true, echo: false });
      return;
    }
    setTurns((t) => [
      ...t,
      { role: "bot", text: "Ok, mình bỏ qua khảo sát. Bạn có thể làm lại bất cứ lúc nào (menu ☰ → Khảo sát)." },
    ]);
  }

  function pickChoice(value: string, label: string) {
    if (value === "__skip") return skipSurvey(label);
    if (value === "__back") return goBack(label);

    if (surveyStage === "q1") {
      const q1 = value as SurveyChoice;
      setSurveyAns({ q1, q2: null });
      if (q1 === "any") {
        setSurveyStage("q3");
        setTurns((t) => [...t, { role: "user", text: label }, q3Turn()]);
      } else {
        setSurveyStage("q2");
        setTurns((t) => [...t, { role: "user", text: label }, q2Turn(q1)]);
      }
    } else if (surveyStage === "q2") {
      setSurveyAns((a) => ({ ...a, q2: value as SurveyChoice }));
      setSurveyStage("q3");
      setTurns((t) => [...t, { role: "user", text: label }, q3Turn()]);
    }
  }

  async function finishSurvey(text: string) {
    const none = /^(không|khong|ko|no|k)$/i.test(text.trim());
    const answers: SurveyAnswers = {
      q1: surveyAns.q1,
      q2: surveyAns.q1 === "any" ? null : surveyAns.q2 ?? "any",
      allergies_text: none ? "" : text,
    };
    setTurns((t) => [...t, { role: "user", text }]);
    setDraft("");
    try {
      const newPref = await submitSurvey(answers);
      setSurveyStage(null);
      if (pendingRandom.current) {
        pendingRandom.current = false;
        setTurns((t) => [
          ...t,
          { role: "bot", text: "Cảm ơn bạn! Dựa trên khảo sát vừa rồi, mình bốc quán cho bạn ngay đây." },
        ]);
        suggestRandom({ pref: newPref, reset: true, echo: false });
        return;
      }
      setTurns((t) => [
        ...t,
        {
          role: "bot",
          text: "Vậy là chúng ta đã sẵn sàng bắt đầu rồi! Bạn có thể làm lại bài khảo sát (menu ☰ → Khảo sát) để thay đổi cách mình tìm kiếm, hoặc nói thẳng với mình trong đoạn chat nhé.",
        },
      ]);
    } catch (e) {
      setTurns((t) => [
        ...t,
        {
          role: "bot",
          text: `Không lưu được khảo sát: ${e instanceof Error ? e.message : "lỗi"}. Bạn gõ lại dị ứng để thử lần nữa.`,
        },
      ]);
    }
  }

  async function submitContribution(e: React.SubmitEvent) {
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
            `Đã lưu quán #${res.id} + ${res.dishes_saved} món. ${locMsg(res)}`,
          );
        } else {
          const res = await contributePlace(payload);
          setContribMsg(`Đã lưu quán (id=${res.id}). ${locMsg(res)}`);
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
        setContribMsg("Đã lưu quán.");
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

  if (screen === "chat" || (screen === "place" && active)) {
    return (
      <>
        {/* ẩn (không huỷ) khung chat khi đang ở trang quán → quay lại vẫn còn danh sách */}
        <div style={{ display: screen === "chat" ? "contents" : "none" }}>
          <ChatHome
            onNewChat={startNewChat}
            userName={user?.name ?? null}
            turns={turns}
            results={ranked}
            ratings={ratings}
            onOpenPlace={(id, mode) => {
              setActiveId(id);
              setPlaceMode(mode);
                setScreen("place");
                    }}
                    onSuggest={startRandomFlow}
                    onReroll={() => suggestRandom()}
                    onSurvey={() => startSurvey(false)}
                    onChoice={pickChoice}
            draft={draft}
            onDraft={setDraft}
            onSend={(t) => void sendChat(t)}
            onLogin={() => setPage("login")}
            onLogout={() => {
              if (useApi) logoutApi();
              else signOut();
              setUser(null);
            }}
            onNavigate={(to: NavTarget) => {
              if (to === "chat") return;
              if (to === "list") setDirectoryHistoryFilter(false);
              setTab(to);
              setScreen("classic");
            }}
          />
        </div>
        {screen === "place" && active && (
          <PlacePage
            mode={placeMode}
            place={active}
            campus={campus}
            rating={ratings[active.id]}
            reviews={activeReviews}
            info={<PlaceInfoText place={active} info={activeInfo} />}
            route={{ coords: routeCoords, meta: routeMeta, loading: routeLoading, error: routeError }}
            onBack={() => setScreen("chat")}
            onSwitch={setPlaceMode}
            loc={userLoc}
            onBigMap={() => {
              setTab("list");
              setScreen("classic");
            }}
          />
        )}
      </>
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
          <button type="button" className="chip" onClick={() => setScreen("chat")}>
            ← Trò chuyện
          </button>
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
      
      {apiError && <p className="error">{apiError}</p>}
      {regenMsg && <p className="muted">{regenMsg}</p>}

      {/* BỐ CỤC MỚI: CỘT TRÁI NỘI DUNG CHÍNH - CỘT PHẢI THANH DANH MỤC (KHÔNG MAP, KHÔNG LỌC KHU VỰC) */}
      <div className="stage-no-map">
        {/* CỘT TRÁI: NỘI DUNG CHÍNH */}
        <main className="main-content-panel">
          {tab === "list" && (
            <div className="ds-quan-container">
              {/* Hàng trên cùng: Ô Tìm kiếm + Nút Thêm mới quán ăn */}
              <div className="ds-quan-toolbar">
                <input
                  className="field grow"
                  type="search"
                  value={directoryQuery}
                  onChange={(e) => setDirectoryQuery(e.target.value)}
                  placeholder="Tìm tên quán, món, địa chỉ…"
                  aria-label="Tìm quán"
                />
                <button
                  type="button"
                  className="btn-primary"
                  onClick={() => setTab("contribute")}
                >
                  + Thêm mới quán ăn
                </button>
              </div>

              {/* Thanh thông tin số lượng & Sắp xếp */}
              <div className="ds-sort-bar">
                <span className="muted">{ranked.length} quán</span>
                <select
                  className="field select"
                  value={sortBy}
                  onChange={(e) => setSortBy(e.target.value as SortKey)}
                  aria-label="Sắp xếp"
                >
                  <option value="near">Gần nhất</option>
                  <option value="price_asc">Giá thấp → cao</option>
                  <option value="price_desc">Giá cao → thấp</option>
                </select>
              </div>

              {/* Danh sách thẻ quán chia 2 cột */}
              <div className="ds-card-list">
                {ranked.map((p) => {
                  const pReviews = reviews.filter((r) => r.placeId === p.id);
                  const ratingAvg =
                    pReviews.length > 0
                      ? (
                          pReviews.reduce((sum, r) => sum + r.rating, 0) /
                          pReviews.length
                        ).toFixed(1)
                      : null;

                  const cleanAddress = splitAddress(p.address).address;
                  const previewDishes = (
                    p as Place & { dishes?: { name: string; price?: number }[] }
                  ).dishes?.slice(0, 3);

                  return (
                    <div
                      key={p.id}
                      role="button"
                      tabIndex={0}
                      className={
                        active?.id === p.id
                          ? "ds-place-card is-on"
                          : "ds-place-card"
                      }
                      onClick={() => setActiveId(p.id)}
                      onKeyDown={(e) => {
                        if (e.key === "Enter") setActiveId(p.id);
                      }}
                    >
                      {/* Cột trái: Hình + Tên quán + Giá + Sao + Địa chỉ */}
                      <div className="ds-card-left">
                        <div className="ds-thumb">
                          {(p as Place & { image_url?: string }).image_url ? (
                            <img
                              src={
                                (p as Place & { image_url?: string }).image_url
                              }
                              alt={p.name}
                            />
                          ) : (
                            <span className="ds-thumb-placeholder">🍜</span>
                          )}
                        </div>

                        <div className="ds-info">
                          <strong className="ds-place-name">{p.name}</strong>
                          <span className="ds-place-price">{priceText(p)}</span>
                          <span className="ds-place-meta">
                            <span className="ds-rating">
                              {ratingAvg ? `${ratingAvg} ★` : "Chưa có ★"}
                            </span>
                            {" · "}
                            <span>Địa chỉ: {cleanAddress || "Đang cập nhật"}</span>
                          </span>
                        </div>
                      </div>

                      {/* Cột phải: Món tiêu biểu + Giá */}
                      <div className="ds-card-right">
                        {previewDishes && previewDishes.length > 0 ? (
                          <ul className="ds-dish-list">
                            {previewDishes.map((d, idx) => (
                              <li key={idx} className="ds-dish-item">
                                <span className="ds-dish-name">{d.name}</span>
                                <span className="ds-dish-price">
                                  {d.price != null ? vnd(d.price) : "—"}
                                </span>
                              </li>
                            ))}
                          </ul>
                        ) : (
                          <div className="ds-no-dishes">
                            <div>Loại: {p.cuisine}</div>
                            <div className="muted">Đang cập nhật menu...</div>
                          </div>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>

              {ranked.length === 0 && (
                <p className="muted">
                  {directoryQuery.trim()
                    ? `Không tìm thấy quán khớp "${directoryQuery.trim()}".`
                    : "Chưa có quán nào trong danh sách."}
                </p>
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
            <div className="stack hx-contrib">
              <h2 className="section">Đóng góp quán mới</h2>
              <p className="muted">
                Thêm quán quanh <strong>{CAMPUSES[campus].short}</strong>.
              </p>
              {!user && (
                <button className="btn-primary" type="button" onClick={() => setPage("login")}>
                  Đăng nhập để đóng góp
                </button>
              )}
              <form className="stack" onSubmit={(e) => void submitContribution(e)}>
                <label>
                  Tên quán
                  <input
                    className="field"
                    required
                    minLength={2}
                    value={contribName}
                    onChange={(e) => setContribName(e.target.value)}
                    placeholder="Cơm tấm cô Năm"
                  />
                </label>
                <label>
                  Loại món
                  <input
                    className="field"
                    required
                    value={contribCuisine}
                    onChange={(e) => setContribCuisine(e.target.value)}
                  />
                </label>
                <label>
                  Địa chỉ đầy đủ (dùng để định vị trên Google Maps)
                  <textarea
                    className="field"
                    required
                    minLength={4}
                    rows={2}
                    value={contribAddress}
                    onChange={(e) => setContribAddress(e.target.value)}
                    placeholder="VD: 227 Nguyễn Văn Cừ, Phường 4, Quận 5"
                  />
                </label>
                {useApi && (
                  <label>
                    Link Google Maps (tùy chọn, để vị trí chính xác hơn)
                    <input
                      className="field"
                      type="url"
                      value={contribMapsUrl}
                      onChange={(e) => setContribMapsUrl(e.target.value)}
                      placeholder="Mở quán trên Google Maps → Chia sẻ → Sao chép liên kết"
                    />
                  </label>
                )}
                <label>
                  Giờ mở
                  <input
                    className="field"
                    value={contribHours}
                    onChange={(e) => setContribHours(e.target.value)}
                  />
                </label>
                <div className="row wrap">
                  <label>
                    Giá từ (đ)
                    <input
                      className="field tiny"
                      type="number"
                      min={0}
                      step={1}
                      placeholder="Bỏ trống nếu chưa rõ"
                      value={contribMin}
                      onChange={(e) => setContribMin(e.target.value)}
                    />
                  </label>
                  <label>
                    Giá đến (đ)
                    <input
                      className="field tiny"
                      type="number"
                      min={0}
                      step={1}
                      placeholder="Bỏ trống nếu chưa rõ"
                      value={contribMax}
                      onChange={(e) => setContribMax(e.target.value)}
                    />
                  </label>
                </div>
                {!useApi && (
                  <label>
                    Cách cổng ~ (m)
                    <input
                      className="field"
                      type="number"
                      min={50}
                      max={1500}
                      step={50}
                      value={contribOffsetM}
                      onChange={(e) => setContribOffsetM(Number(e.target.value) || 200)}
                    />
                  </label>
                )}
                <label>
                  Ghi chú
                  <input
                    className="field"
                    value={contribNote}
                    onChange={(e) => setContribNote(e.target.value)}
                    placeholder="Món đáng thử…"
                  />
                </label>

                <div className="menu-scan-box">
                  <strong>Ảnh menu</strong>
                  <p className="muted">
                    Menu nhiều trang? Chọn nhiều ảnh một lúc hoặc bấm chọn thêm nhiều lần (tối đa
                    10 ảnh).
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
                      {scanBusy ? "Đang đọc menu…" : `Đọc menu (${menuFiles.length} ảnh)`}
                    </button>
                  )}
                  {scanBusy && (
                    <p className="muted">Đang đọc ảnh, có thể mất vài chục giây…</p>
                  )}
                  {scanMeta && (
                    <div className="stack">
                      <p className="muted">Thông tin đọc được (có thể sửa):</p>
                      <input
                        className="field"
                        placeholder="Số điện thoại"
                        value={scanMeta.phone}
                        onChange={(e) => setScanMeta({ ...scanMeta, phone: e.target.value })}
                      />
                      <input
                        className="field"
                        placeholder="Giờ mở ghi trên menu"
                        value={scanMeta.hours}
                        onChange={(e) => setScanMeta({ ...scanMeta, hours: e.target.value })}
                      />
                      <textarea
                        className="field"
                        rows={2}
                        placeholder="Ghi chú của quán (freeship, phụ thu…)"
                        value={scanMeta.notes}
                        onChange={(e) => setScanMeta({ ...scanMeta, notes: e.target.value })}
                      />
                    </div>
                  )}

                  {scannedDishes.length > 0 && (
                    <div className="dish-list">
                      <p className="hx-legend">
                        <b>Đã đọc {scannedDishes.length} món.</b> Mỗi món gồm{" "}
                        <b>Tên món</b>, <b>Loại</b> (nhóm trên menu, ví dụ Cơm, Nước uống,
                        Topping) và <b>Giá (đ)</b>. Giá ghi theo nghìn đồng trên menu (ví dụ
                        "35") được hiểu là 35.000đ. Ô viền cam là món AI chưa đọc được giá, bạn
                        hãy nhập lại. <b>Thành phần</b> là tùy chọn, chỉ nhập nếu bạn biết; dùng
                        để lọc dị ứng, nên hãy nhập thật chính xác. Khoảng giá của quán tự tính từ
                        các món này.
                      </p>

                      {scannedDishes.map((d, i) => {
                        const patch = (p: Partial<ScannedDish>) =>
                          setScannedDishes((prev) =>
                            prev.map((x, j) => (j === i ? { ...x, ...p } : x)),
                          );
                        return (
                          <div key={i} className="hx-dish-card">
                            <div className="hx-dish-grid">
                              <label>
                                <span>Tên món</span>
                                <input
                                  className="field"
                                  placeholder="Tên món"
                                  value={d.name}
                                  onChange={(e) => patch({ name: e.target.value })}
                                />
                              </label>
                              <label>
                                <span>Loại</span>
                                <input
                                  className="field tiny"
                                  placeholder="VD: Cơm"
                                  value={d.category ?? ""}
                                  onChange={(e) => patch({ category: e.target.value || null })}
                                />
                              </label>
                              <label className={d.price == null ? "is-warn" : ""}>
                                <span>Giá (đ){d.price == null ? " · chưa rõ" : ""}</span>
                                <input
                                  className="field tiny"
                                  type="number"
                                  min={0}
                                  placeholder="35000"
                                  value={d.price ?? ""}
                                  onChange={(e) =>
                                    patch({
                                      price: e.target.value === "" ? null : Number(e.target.value),
                                    })
                                  }
                                />
                              </label>
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

                            {d.ingredients_text === undefined ? (
                              <button
                                type="button"
                                className="hx-ing-add"
                                onClick={() => patch({ ingredients_text: "" })}
                              >
                                + Nhập thành phần
                              </button>
                            ) : (
                              <label>
                                <span>Thành phần (tùy chọn, cách nhau bằng dấu phẩy)</span>
                                <input
                                  className="field"
                                  placeholder="VD: sườn, bì, trứng, đồ chua"
                                  value={d.ingredients_text}
                                  onChange={(e) => patch({ ingredients_text: e.target.value })}
                                />
                              </label>
                            )}
                          </div>
                        );
                      })}

                      <button
                        type="button"
                        className="chip"
                        onClick={() =>
                          setScannedDishes((prev) => [...prev, { name: "", price: null }])
                        }
                      >
                        + Thêm món
                      </button>
                    </div>
                  )}
                </div>

                {contribMsg && (
                  <p
                    className={
                      /lỗi|loi|cần|nhanh|vượt|trùng|tải cao|phải|không|khong|thất bại/i.test(
                        contribMsg,
                      )
                        ? "error"
                        : "muted"
                    }
                  >
                    {contribMsg}
                  </p>
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
                        setDirectoryHistoryFilter(true);
                        setDirectoryQuery("");
                        setBudget(h.budget);
                        setRadius(h.radiusM);
                        setTab("list");
                      }}
                    >
                      <strong>{h.query}</strong>
                      <span>
                        {h.campus === "q5" ? "Quận 5" : "Làng ĐH"} · {h.budget == null ? "Không giới hạn giá" : vnd(h.budget)} · {h.radiusM == null ? "Không giới hạn bán kính" : `${h.radiusM}m`}
                      </span>
                    </button>
                  ))}
                  <button
                    type="button"
                    className="chip"
                    onClick={() =>
                      void remember(`Thủ công ${CAMPUSES[campus].short} ${budget == null ? "không giới hạn giá" : vnd(budget)} · ${radius == null ? "không giới hạn bán kính" : `${radius}m`}`)
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
              <a
                className="chip"
                target="_blank"
                rel="noreferrer"
                href={`https://www.google.com/maps/dir/?api=1&origin=${userLoc.origin.lat},${userLoc.origin.lng}&destination=${active.lat},${active.lng}&travelmode=walking`}
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
        </main>

        {/* CỘT PHẢI: THANH DANH MỤC CHUYỂN MỤC */}
        <aside className="right-nav-sidebar">
          <p className="nav-sidebar-title">Danh mục</p>
          <div className="right-tabs">
            {(["list", "chat", "contribute", "me"] as const).map((id) => (
              <button
                key={id}
                type="button"
                className={tab === id ? "right-tab-btn is-on" : "right-tab-btn"}
                onClick={() => {
                  if (id === "chat") {
                    setScreen("chat");
                  } else {
                    if (id === "list") setDirectoryHistoryFilter(false);
                    setTab(id);
                  }
                }}
              >
                {id === "list"
                  ? "Danh sách quán"
                  : id === "chat"
                    ? "Khung chat trợ lý"
                    : id === "contribute"
                      ? "Thêm mới quán"
                      : "Của tôi"}
              </button>
            ))}
          </div>
        </aside>
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

  async function submit(e: React.SubmitEvent) {
    e.preventDefault();
    setError("");
    setBusy(true);
    try {
      if (useApi) {
        try {
          const cred =
            mode === "up"
              ? await createUserWithEmailAndPassword(fbAuth, email, password)
              : await signInWithEmailAndPassword(fbAuth, email, password);
          if (mode === "up") {
            await updateProfile(cred.user, { displayName: name });
            await sendEmailVerification(cred.user);
          }
          const data = await loginWithFirebaseToken(await cred.user.getIdToken(true));
          onDone(data.user);
        } catch (err) {
          const code = (err as { code?: string }).code;
          const notInFirebase =
            code === "auth/invalid-credential" || code === "auth/user-not-found";
          if (mode === "in" && notInFirebase) {
            // Có thể là tài khoản cũ (trước khi có Firebase): thử mật khẩu cũ trên MySQL
            const legacy = await apiLogin(email, password);
            try {
              const cred = await createUserWithEmailAndPassword(fbAuth, email, password);
              await sendEmailVerification(cred.user);
            } catch {
              /* đã có trên Firebase thì bỏ qua */
            }
            onDone(legacy.user);
            return;
          }
          if (code === "auth/email-already-in-use") {
            throw new Error('Email này đã có tài khoản. Hãy bấm "Đã có tài khoản? Đăng nhập".');
          }
          throw err;
        }
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
          {/* {useApi
            ? "Tài khoản lưu trên MySQL qua API Python."
            : "Chế độ offline — tài khoản chỉ trên trình duyệt này."} */}
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