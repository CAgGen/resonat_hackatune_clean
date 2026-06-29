// Typed wrappers for backend endpoints. base goes through the Vite proxy (see vite.config.ts).
const BASE = "/api";

export type SoftTarget = { dim: string; value: string; weight: number };
export type QueryCard = {
  interpretation_plain: string;
  free_text_query: string;
  soft_targets: SoftTarget[];
  negatives: Record<string, unknown>[];
};
export type IntentResponse = {
  session_id: string;
  whiteboard_posts: unknown[];
  query_card: QueryCard;
};
export type RecommendationCard = {
  track_id: string;
  cyanite_id: string;
  title: string;
  artist: string;
  source: "free_text" | "similar" | "profile_semantic" | string;
  score: number;
  why?: string;
};
export type CardsResponse = {
  cards: RecommendationCard[];
  candidate_pool_size: number;
};
export type MoodSegment = { t: number; label: string };
export type ExplanationResponse = {
  why_text: string;
  evidence: { source: string; detail: string }[];
  segments?: MoodSegment[];
};

async function post<T>(path: string, body: unknown): Promise<T> {
  const r = await fetch(BASE + path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!r.ok) {
    let detail = "";
    try {
      const body = (await r.json()) as { detail?: unknown };
      detail = typeof body.detail === "string" ? body.detail : "";
    } catch {
      detail = "";
    }
    throw new Error(detail || `${path} -> ${r.status}`);
  }
  return r.json();
}

export const intent = (text: string, user_id = "demo") =>
  post<IntentResponse>("/intent", { text, user_id });

export const confirm = (session_id: string) =>
  post<CardsResponse>("/intent/confirm", { session_id });

export type FeedbackMode = "normal" | "anti_addiction";

export const feedback = (
  session_id: string,
  track_id: string,
  verdict: "like" | "dislike",
  mode: FeedbackMode = "normal",
) => post<CardsResponse>("/feedback", { session_id, track_id, verdict, mode });

export const explain = (session_id: string, track_id: string) =>
  post<ExplanationResponse>("/explain", { session_id, track_id });

export const yourSound = (user_id = "demo") =>
  fetch(`${BASE}/your-sound?user_id=${user_id}`).then((r) => r.json());

export type FinishRoundResponse = { memory_md: string; liked: string[] };

// "Finish this round": persist selected songs as feeling memory and return the updated profile.
export const finishRound = (session_id: string) =>
  post<FinishRoundResponse>("/round/finish", { session_id });

export type SoundsLikeYouResponse = {
  cards: RecommendationCard[];
  memory_md: string;
};

export const soundsLikeYou = (user_id = "demo") =>
  fetch(`${BASE}/sounds-like-you?user_id=${user_id}`).then(
    (r) => r.json() as Promise<SoundsLikeYouResponse>,
  );

export const explainSoundsLikeYou = (user_id: string, cyanite_id: string) =>
  post<ExplanationResponse>("/explain-sounds-like-you", { user_id, cyanite_id });
