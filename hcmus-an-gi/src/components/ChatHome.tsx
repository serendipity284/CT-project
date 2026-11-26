import { useEffect, useRef, useState } from "react";
import { Menu, MessageCircle, Search, PlusCircle, User as UserIcon, Send, X, ClipboardList } from "lucide-react";
import type { ChatTurn } from "../lib/chat-intent";
import type { Place } from "../lib/places-data";


export type NavTarget = "chat" | "list" | "contribute" | "me";

type ResultPlace = Place & { meters: number };

type Props = {
  onNewChat: () => void;
  userName: string | null;
  results: ResultPlace[];
  ratings: Record<number, { avg: number; count: number }>;
  /** Bấm "Chi tiết" / "Chỉ đường" trong popup → App chuyển sang trang tương ứng */
  onOpenPlace: (id: number, mode: "detail" | "route") => void;
  turns: ChatTurn[];
  draft: string;
  onDraft: (v: string) => void;
  onSend: (text: string) => void;
  onLogin: () => void;
  onLogout: () => void;
  onNavigate: (to: NavTarget) => void;
  onSurvey: () => void;
    onChoice: (value: string, label: string) => void;
    /** nút 🎲 chính: khảo sát trước rồi mới random */
    onSuggest: () => void;
    /** "Random lại": bốc lô 15 quán khác, giữ nguyên khảo sát vừa làm */
    onReroll: () => void;
};

/** Logo bot: nắp cloche + muỗng + nĩa (giống mockup). */
function BotAvatar() {
  return (
    <svg className="hx-avatar" viewBox="0 0 80 44" aria-hidden="true">
      {/* <rect width="80" height="44" fill="#fff" /> */}
      {/* muỗng */}
      <ellipse cx="9" cy="12" rx="4" ry="5.5" fill="none" stroke="#6b4129" strokeWidth="2" />
      <path d="M9 18v20" stroke="#6b4129" strokeWidth="2.4" strokeLinecap="round" />
      {/* nĩa */}
      <path d="M69 6v10M73 6v10M77 6v10M69 16q4 4 8 0M73 20v18" fill="none"
        stroke="#6b4129" strokeWidth="2" strokeLinecap="round" />
      {/* cloche */}
      <path d="M20 32a20 20 0 0 1 40 0z" fill="#e4c9a8" stroke="#6b4129" strokeWidth="2" />
      <circle cx="40" cy="10" r="2.6" fill="#6b4129" />
      <path d="M16 36h48" stroke="#6b4129" strokeWidth="3" strokeLinecap="round" />
    </svg>
  );
}

const k = (n: number) => `${Math.round(n / 1000)}k`;
function priceShort(p: { price_min: number; price_max: number }) {
  if (!(p.price_max > 0)) return "Chưa rõ giá";
  return p.price_min === p.price_max ? k(p.price_min) : `${k(p.price_min)} - ${k(p.price_max)}`;
}

function PlaceThumb({ url, alt }: { url?: string | null; alt: string }) {
  const [bad, setBad] = useState(false);
  if (url && !bad) {
    return <img className="hx-thumb" src={url} alt={alt} onError={() => setBad(true)} />;
  }
  return <div className="hx-thumb hx-thumb-empty" aria-hidden="true">🍜</div>;
}

function Star() {
  return (
    <svg className="hx-star" viewBox="0 0 24 24" aria-hidden="true">
      <path d="M12 2l3.1 6.6 7.2.9-5.3 5 1.4 7.1L12 18l-6.4 3.6L7 14.5l-5.3-5 7.2-.9z" fill="#f2dc2c" />
    </svg>
  );
}

export function ChatHome({
    userName, results, ratings, onOpenPlace, turns, draft, onDraft, onSend, onLogin, onLogout, onNavigate, onSurvey, onChoice, onSuggest, onReroll, onNewChat
}: Props) {
  const [open, setOpen] = useState(false);
  // popup bên phải danh sách: quán đang chọn + vị trí dọc (px, tính từ đầu khung danh sách)
  const [pop, setPop] = useState<{ id: number; top: number } | null>(null);
  const wrapRef = useRef<HTMLDivElement>(null);
  const popScroll = useRef(0); // scrollTop của danh sách lúc mở popup

  function togglePop(id: number, card: HTMLElement) {
    if (pop?.id === id) return setPop(null);
    const wrap = wrapRef.current?.getBoundingClientRect();
    const c = card.getBoundingClientRect();
    if (!wrap) return;
    popScroll.current = card.parentElement?.scrollTop ?? 0;
    const mid = c.top - wrap.top + c.height / 2;
    setPop({ id, top: Math.min(Math.max(mid, 56), Math.max(wrap.height - 56, 56)) });
  }
  const endRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [turns.length]);

  const go = (to: NavTarget) => {
    setOpen(false);
    onNavigate(to);
  };

  return (
    <div className="hx-app">
      <header className="hx-header">
        <h1 className="hx-logo">HCMUS ĂN GÌ</h1>
        <div className="hx-auth">
          {userName ? (
            <>
              <span className="hx-user">{userName}</span>
              <button type="button" className="hx-auth-btn" onClick={onLogout}>ĐĂNG XUẤT</button>
            </>
          ) : (
            <button type="button" className="hx-auth-btn" onClick={onLogin}>
              ĐĂNG KÝ / ĐĂNG NHẬP
            </button>
          )}
        </div>
      </header>

      <div className="hx-body">
        <nav className={open ? "hx-rail is-open" : "hx-rail"} aria-label="Menu">
          <button
            type="button"
            className="hx-burger"
            aria-label={open ? "Đóng menu" : "Mở menu"}
            aria-expanded={open}
            onClick={() => setOpen((v) => !v)}
          >
            {open ? <X size={30} /> : <Menu size={30} />}
          </button>
          {open && (
            <ul className="hx-menu">
              <li><button type="button" onClick={() => go("chat")}><MessageCircle size={18} /> Trò chuyện</button></li>
              <li><button type="button" onClick={() => go("list")}><Search size={18} /> Quán &amp; bản đồ</button></li>
              <li><button type="button" onClick={() => go("contribute")}><PlusCircle size={18} /> Đóng góp</button></li>
              <li><button type="button" onClick={() => go("me")}><UserIcon size={18} /> Của tôi</button></li>
              <li><button type="button" onClick={() => { setOpen(false); onSurvey(); }}><ClipboardList size={18} /> Khảo sát</button></li>
            </ul>
          )}
        </nav>

        <main className="hx-main">
          <div className="hx-thread">
            <div className="hx-row bot">
              <BotAvatar />
              <p className="hx-bubble bot">Tôi có thể giúp gì cho bạn ?</p>
            </div>
            {turns.map((t, i) => {
              if (i === 0) return null; // lời chào đã hiện ở trên
              const isLastList = t.list && i === turns.map((x) => !!x.list).lastIndexOf(true);
              // lượt random: hiện đúng các quán đã bốc (theo thứ tự bốc); lượt thường: top 15 theo kết quả lọc
              const shown: ResultPlace[] = t.picks
                ? t.picks
                    .map((id) => results.find((p) => p.id === id))
                    .filter((p): p is ResultPlace => !!p)
                : results.slice(0, 15);
              return (
                <div key={i} className="hx-block">
                  <div className={t.role === "bot" ? "hx-row bot" : "hx-row me"}>
                    {t.role === "bot" && <BotAvatar />}
                    <p className={t.role === "bot" ? "hx-bubble bot" : "hx-bubble me"}>{t.text}</p>
                  </div>
                  {t.choices && i === turns.length - 1 && (
                    <div className="hx-choices">
                      {t.choices.map((c) => (
                        <button key={c.value} type="button" onClick={() => onChoice(c.value, c.label)}>
                          {c.label}
                        </button>
                      ))}
                    </div>
                  )}
                      {t.suggestion && i === turns.length - 1 && (
                          <div className="hx-choices">
                              <button type="button" onClick={() => onOpenPlace(t.suggestion!.id, "detail")}>Chi tiết</button>
                              <button type="button" onClick={() => onOpenPlace(t.suggestion!.id, "route")}>Chỉ đường</button>
                              <button type="button" onClick={onReroll}>🎲 Random lại</button>
                          </div>
                      )}
                  {isLastList && (
                    <div className="hx-results-wrap" ref={wrapRef}>
                      <div className="hx-results" onScroll={(e) => {
                          if (Math.abs(e.currentTarget.scrollTop - popScroll.current) > 4) setPop(null);
                        }}>
                        {shown.length === 0 && (
                          <p className="hx-empty">Không tìm thấy quán phù hợp. Bạn thử kiểm tra tên quán, ngân sách hoặc khoảng cách nhé.</p>
                        )}
                        {shown.map((p) => {
                          const r = ratings[p.id];
                          return (
                            <button
                              key={p.id}
                              type="button"
                              className={pop?.id === p.id ? "hx-card is-open" : "hx-card"}
                              aria-expanded={pop?.id === p.id}
                              onClick={(e) => togglePop(p.id, e.currentTarget)}
                            >
                              <div className="hx-card-info">
                                <strong className="hx-card-name">{p.name}</strong>
                                <span className="hx-card-price">{priceShort(p)}</span>
                                <div className="hx-card-meta">
                                  <span className="hx-rate">
                                    {r ? r.avg.toFixed(1) : "—"} <Star />
                                  </span>
                                  <span>{p.meters} m</span>
                                </div>
                              </div>
                              <PlaceThumb url={p.image_url} alt={p.name} />
                            </button>
                          );
                        })}
                      </div>
                      {t.picks && i === turns.length - 1 && (
                        <div className="hx-choices">
                          <button type="button" onClick={onReroll}>🎲 Random lại 5 quán khác</button>
                        </div>
                      )}
                      {pop && (
                        <div className="hx-pop" style={{ top: pop.top }} role="dialog">
                          <button type="button" className="primary"
                            onClick={() => { onOpenPlace(pop.id, "detail"); setPop(null); }}>
                            Chi tiết
                          </button>
                          <button type="button"
                            onClick={() => { onOpenPlace(pop.id, "route"); setPop(null); }}>
                            Chỉ đường
                          </button>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              );
            })}
            <div ref={endRef} />
          </div>

                  <div className="hx-choices">
                      <button type="button" onClick={() => {
                        onNewChat();
                        setOpen(false);
                        setPop(null);
                        inputRef.current?.focus();
                      }}>+ Chat mới</button>
                      <button type="button" onClick={() => onSuggest()}>🎲 Gợi ý ngẫu nhiên cho tôi</button>
                  </div>

          <form
            className="hx-composer"
            onSubmit={(e) => {
              e.preventDefault();
              onSend(draft);
            }}
          >
            <input
              ref={inputRef}
              value={draft}
              onChange={(e) => onDraft(e.target.value)}
              placeholder="Quận 5, dưới 35k, 400m…"
              aria-label="Nhập câu hỏi"
            />
            <button type="submit" aria-label="Gửi"><Send size={20} /></button>
          </form>
        </main>
      </div>
    </div>
  );
}
