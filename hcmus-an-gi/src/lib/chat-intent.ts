import { CAMPUSES, type CampusId } from "./campuses";

export type Intent = {
  campus?: CampusId;
  budget?: number;
  radiusM?: number;
};

export type ChatTurn = { role: "user" | "bot"; text: string };

const CAMPUS_Q5 = /quận\s*5|q\.?\s*5|nguyễn văn cừ|nvc/i;
const CAMPUS_LANG = /làng|linh trung|thủ đức|lang dai hoc|làng đại học/i;

function parseMoney(text: string): number | undefined {
  const under = text.match(
    /(?:dưới|duoi|tối đa|toi da|max|<)\s*(\d+(?:[.,]\d+)?)\s*(k|nghìn|nghin|tr)?/i,
  );
  const plain = text.match(/(\d+(?:[.,]\d+)?)\s*(k|nghìn|nghin|triệu|trieu|tr)\b/i);
  const hit = under ?? plain;
  if (!hit) return undefined;
  const raw = Number(hit[1].replace(",", "."));
  const unit = (hit[2] ?? "").toLowerCase();
  if (unit.startsWith("tr")) return Math.round(raw * 1_000_000);
  if (unit === "k" || unit.startsWith("ngh") || unit.startsWith("nghin"))
    return Math.round(raw * 1000);
  if (raw < 500) return Math.round(raw * 1000);
  return Math.round(raw);
}

function parseRadius(text: string): number | undefined {
  const m = text.match(/(\d+(?:[.,]\d+)?)\s*(km|m|mét|met)\b/i);
  if (!m) return undefined;
  const n = Number(m[1].replace(",", "."));
  const unit = m[2].toLowerCase();
  if (unit === "km") return Math.round(n * 1000);
  return Math.round(n);
}

export function readIntent(text: string, prev: Intent): Intent {
  const next = { ...prev };
  if (CAMPUS_Q5.test(text)) next.campus = "q5";
  if (CAMPUS_LANG.test(text)) next.campus = "lang";
  const money = parseMoney(text);
  if (money) next.budget = money;
  const radius = parseRadius(text);
  if (radius) next.radiusM = radius;
  return next;
}

export function missingPrompt(intent: Intent): string | null {
  if (!intent.campus) {
    return "Bạn đang ở cơ sở nào — Quận 5 (Nguyễn Văn Cừ) hay Làng Đại học?";
  }
  if (!intent.budget) {
    return `Ngân sách tối đa mỗi người là bao nhiêu? Ví dụ: dưới 40k. Đang lọc quanh ${CAMPUSES[intent.campus].short}.`;
  }
  if (!intent.radiusM) {
    return "Bạn muốn đi bộ trong bao xa? Ví dụ: 500m hoặc 1km.";
  }
  return null;
}

export function replyFor(
  text: string,
  prev: Intent,
): { intent: Intent; say: string; ready: boolean } {
  const intent = readIntent(text, prev);
  const ask = missingPrompt(intent);
  if (ask) return { intent, say: ask, ready: false };
  const c = CAMPUSES[intent.campus!];
  return {
    intent,
    say: `Được. Mình ghim các quán quanh ${c.short}, tối đa ${intent.budget!.toLocaleString("vi-VN")}đ, trong ${intent.radiusM}m. Chọn một quán để xem đường đi trên bản đồ nghiêng.`,
    ready: true,
  };
}
