/** Lưu local (demo không cần backend). Thay bằng API khi có MySQL. */

export type Review = {
  id: number;
  placeId: number;
  authorName: string;
  rating: number;
  body: string;
  createdAt: string;
};

export type HistoryItem = {
  id: number;
  campus: string;
  budget: number;
  radiusM: number;
  query: string;
  createdAt: string;
};

export type User = {
  id: string;
  email: string;
  name: string;
};

const K = {
  user: "hcmus_user",
  saves: "hcmus_saves",
  history: "hcmus_history",
  reviews: "hcmus_reviews",
  users: "hcmus_users_db",
};

function read<T>(key: string, fallback: T): T {
  try {
    const raw = localStorage.getItem(key);
    if (!raw) return fallback;
    return JSON.parse(raw) as T;
  } catch {
    return fallback;
  }
}

function write(key: string, value: unknown) {
  localStorage.setItem(key, JSON.stringify(value));
}

export function getCurrentUser(): User | null {
  return read<User | null>(K.user, null);
}

export function setCurrentUser(user: User | null) {
  if (!user) localStorage.removeItem(K.user);
  else write(K.user, user);
}

type StoredUser = User & { password: string };

export function signUp(email: string, password: string, name: string): { ok: true; user: User } | { ok: false; error: string } {
  const users = read<StoredUser[]>(K.users, []);
  if (users.some((u) => u.email.toLowerCase() === email.toLowerCase())) {
    return { ok: false, error: "Email đã được dùng." };
  }
  if (password.length < 6) return { ok: false, error: "Mật khẩu tối thiểu 6 ký tự." };
  const user: StoredUser = {
    id: crypto.randomUUID(),
    email,
    name,
    password,
  };
  users.push(user);
  write(K.users, users);
  const pub = { id: user.id, email: user.email, name: user.name };
  setCurrentUser(pub);
  return { ok: true, user: pub };
}

export function signIn(email: string, password: string): { ok: true; user: User } | { ok: false; error: string } {
  const users = read<StoredUser[]>(K.users, []);
  const found = users.find(
    (u) => u.email.toLowerCase() === email.toLowerCase() && u.password === password,
  );
  if (!found) return { ok: false, error: "Email hoặc mật khẩu không đúng." };
  const pub = { id: found.id, email: found.email, name: found.name };
  setCurrentUser(pub);
  return { ok: true, user: pub };
}

export function signOut() {
  setCurrentUser(null);
}

export function getSaves(userId: string): number[] {
  const all = read<Record<string, number[]>>(K.saves, {});
  return all[userId] ?? [];
}

export function toggleSave(userId: string, placeId: number): number[] {
  const all = read<Record<string, number[]>>(K.saves, {});
  const list = new Set(all[userId] ?? []);
  if (list.has(placeId)) list.delete(placeId);
  else list.add(placeId);
  all[userId] = [...list];
  write(K.saves, all);
  return all[userId];
}

export function getHistory(userId: string): HistoryItem[] {
  const all = read<Record<string, HistoryItem[]>>(K.history, {});
  return all[userId] ?? [];
}

export function addHistory(
  userId: string,
  item: Omit<HistoryItem, "id" | "createdAt">,
): HistoryItem[] {
  const all = read<Record<string, HistoryItem[]>>(K.history, {});
  const list = all[userId] ?? [];
  const row: HistoryItem = {
    ...item,
    id: Date.now(),
    createdAt: new Date().toISOString(),
  };
  all[userId] = [row, ...list].slice(0, 30);
  write(K.history, all);
  return all[userId];
}

export function getReviews(): Review[] {
  return read<Review[]>(K.reviews, []);
}

export function addReview(input: Omit<Review, "id" | "createdAt">): Review[] {
  const list = getReviews();
  const row: Review = {
    ...input,
    id: Date.now(),
    createdAt: new Date().toISOString(),
  };
  const next = [row, ...list].slice(0, 200);
  write(K.reviews, next);
  return next;
}
