import { useEffect, useRef, useState } from "react";
import { Menu, MessageCircle, Search, PlusCircle, User as UserIcon, Send, X } from "lucide-react";
import type { ChatTurn } from "../lib/chat-intent";

export type NavTarget = "chat" | "list" | "contribute" | "me";

type Props = {
  userName: string | null;
  turns: ChatTurn[];
  draft: string;
  onDraft: (v: string) => void;
  onSend: (text: string) => void;
  onLogin: () => void;
  onLogout: () => void;
  onNavigate: (to: NavTarget) => void;
};

/** Logo bot: nắp cloche + muỗng + nĩa (giống mockup). */
function BotAvatar() {
  return (
    <svg className="hx-avatar" viewBox="0 0 80 44" aria-hidden="true">
      <rect width="80" height="44" fill="#fff" />
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

export function ChatHome({
  userName, turns, draft, onDraft, onSend, onLogin, onLogout, onNavigate,
}: Props) {
  const [open, setOpen] = useState(false);
  const endRef = useRef<HTMLDivElement>(null);

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
            </ul>
          )}
        </nav>

        <main className="hx-main">
          <div className="hx-thread">
            <div className="hx-row bot">
              <BotAvatar />
              <p className="hx-bubble bot">Tôi có thể giúp gì cho bạn ?</p>
            </div>
            {turns.slice(1).map((t, i) => (
              <div key={i} className={t.role === "bot" ? "hx-row bot" : "hx-row me"}>
                {t.role === "bot" && <BotAvatar />}
                <p className={t.role === "bot" ? "hx-bubble bot" : "hx-bubble me"}>{t.text}</p>
              </div>
            ))}
            <div ref={endRef} />
          </div>

          <form
            className="hx-composer"
            onSubmit={(e) => {
              e.preventDefault();
              onSend(draft);
            }}
          >
            <input
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
