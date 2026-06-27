// 后端 4 端点的 typed 封装。base 走 Vite 代理（见 vite.config.ts）。
const BASE = "/api";

export type SoftTarget = { dim: string; value: string; weight: number };
export type QueryCard = {
  interpretation_plain: string;
  free_text_query: string;
  soft_targets: SoftTarget[];
  negatives: Record<string, unknown>[];
};

async function post<T>(path: string, body: unknown): Promise<T> {
  const r = await fetch(BASE + path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!r.ok) throw new Error(`${path} → ${r.status}`);
  return r.json();
}

export const intent = (text: string, user_id = "demo") =>
  post<QueryCard>("/intent", { text, user_id });

export const confirm = (card: QueryCard) =>
  post<{ session_id: string; cards: unknown[] }>("/intent/confirm", card);

export const feedback = (session_id: string, track_id: string, verdict: "like" | "dislike") =>
  post<{ cards: unknown[] }>("/feedback", { session_id, track_id, verdict });

export const yourSound = (user_id = "demo") =>
  fetch(`${BASE}/your-sound?user_id=${user_id}`).then((r) => r.json());
