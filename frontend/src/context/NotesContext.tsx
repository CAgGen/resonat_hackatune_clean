import {
  createContext,
  useContext,
  useEffect,
  useRef,
  useState,
} from "react";
import type { ReactNode } from "react";
import type { Note } from "../types";
import type {
  ExplanationResponse,
  FeedbackMode,
  QueryCard,
  RecommendationCard,
} from "../api";
import { confirm, explain, explainSoundsLikeYou, feedback, finishRound, intent, soundsLikeYou } from "../api";

const joinNotes = (notes: Note[]): string =>
  notes
    .map((note) => note.body.trim())
    .filter(Boolean)
    .join("; ");

const MAX_NOTES = 6;
// Local fallback used when the backend (/intent) isn't reachable, so the
// front end stays testable on its own.
const buildPseudoExplanation = (notes: Note[]): string => {
  const text = joinNotes(notes);
  if (!text) return "";
  return `A search for music shaped around: ${text}. We'll prioritize tracks whose mood, energy, instrumentation, and vocal presence match that brief.`;
};

interface NotesContextValue {
  notes: Note[];
  explanation: string;
  card: QueryCard | null;
  sessionId: string | null;
  cards: RecommendationCard[];
  likedCards: RecommendationCard[];
  isLoadingCards: boolean;
  isBuilding: boolean;
  cardsError: string;
  memoryMd: string;
  soundsLikeYouCards: RecommendationCard[];
  likeSoundsLikeYou: (card: RecommendationCard) => void;
  dismissSoundsLikeYou: (card: RecommendationCard) => void;
  isFinishingRound: boolean;
  resetRound: () => void;
  confirmSound: () => Promise<boolean>;
  completeRound: () => Promise<string | null>;
  sendFeedback: (
    trackId: string,
    verdict: "like" | "dislike",
    mode?: FeedbackMode,
  ) => Promise<void>;
  unlikeTrack: (trackId: string) => void;
  explainTrack: (trackId: string) => Promise<ExplanationResponse>;
  explainSoundsLikeYouTrack: (cyaniteId: string) => Promise<ExplanationResponse>;
  explanationsByTrackId: Record<string, ExplanationResponse>;
  addNote: () => void;
  updateNote: (id: string, body: string) => void;
  lockNote: (id: string) => void;
  finishEditing: () => void;
  buildPseudoExplanation: (notes: Note[]) => string;
}

const NotesContext = createContext<NotesContextValue | null>(null);

export const NotesProvider = ({ children }: { children: ReactNode }) => {
  const [notes, setNotes] = useState<Note[]>([]);
  const [explanation, setExplanation] = useState("");
  const [card, setCard] = useState<QueryCard | null>(null);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [cards, setCards] = useState<RecommendationCard[]>([]);
  const [likedCards, setLikedCards] = useState<RecommendationCard[]>([]);
  const [isLoadingCards, setIsLoadingCards] = useState(false);
  const [isBuilding, setIsBuilding] = useState(false);
  const [cardsError, setCardsError] = useState("");
  const [memoryMd, setMemoryMd] = useState("");
  const [soundsLikeYouCards, setSoundsLikeYouCards] = useState<
    RecommendationCard[]
  >([]);
  const [isFinishingRound, setIsFinishingRound] = useState(false);
  const [explanationsByTrackId, setExplanationsByTrackId] = useState<
    Record<string, ExplanationResponse>
  >({});

  // Keep a live ref to notes so the idle timer / blur handler read fresh content.
  const notesRef = useRef(notes);
  useEffect(() => {
    notesRef.current = notes;
  }, [notes]);

  // 3-second "stopped typing" timer.
  const idleTimer = useRef<number | null>(null);
  const clearIdleTimer = () => {
    if (idleTimer.current !== null) {
      window.clearTimeout(idleTimer.current);
      idleTimer.current = null;
    }
  };
  useEffect(() => clearIdleTimer, []);

  // "Finish edit": compile the memos into an explanation via /intent,
  // falling back to a local pseudo explanation when the backend is offline.
  const finishEditing = async (): Promise<string | null> => {
    clearIdleTimer();
    const text = joinNotes(notesRef.current);
    if (!text) {
      setCard(null);
      setExplanation("");
      setSessionId(null);
      setCards([]);
      setLikedCards([]);
      setCardsError("");
      setExplanationsByTrackId({});
      return null;
    }
    setIsBuilding(true);
    try {
      const result = await intent(text);
      setSessionId(result.session_id);
      setCard(result.query_card);
      setCards([]);
      setLikedCards([]);
      setCardsError("");
      setExplanationsByTrackId({});
      setExplanation(result.query_card.interpretation_plain);
      return result.session_id;
    } catch {
      // Backend not running — show the local pseudo explanation instead.
      setCard(null);
      setExplanation(buildPseudoExplanation(notesRef.current));
      return null;
    } finally {
      setIsBuilding(false);
    }
  };

  const confirmSound = async () => {
    let activeSessionId = sessionId;
    if (!activeSessionId) {
      activeSessionId = await finishEditing();
    }
    if (!activeSessionId) return false;
    setIsLoadingCards(true);
    setCardsError("");
    try {
      const result = await confirm(activeSessionId);
      setCards(result.cards);
      return result.cards.length > 0;
    } catch (error) {
      const message = error instanceof Error ? error.message : "Failed to load recommendations.";
      setCards([]);
      setCardsError(message);
      throw new Error(message);
    } finally {
      setIsLoadingCards(false);
    }
  };

  // 「完成本轮」：把这一轮选的歌落成「感觉」记忆，拿回更新后的画像。
  const completeRound = async (): Promise<string | null> => {
    if (!sessionId) return null;
    setIsFinishingRound(true);
    try {
      const result = await finishRound(sessionId);
      setMemoryMd(result.memory_md);
      // sounds like you：用刚写好的画像搜一小串「AI 眼中的你本人」候选。失败不影响完成本轮。
      soundsLikeYou()
        .then((res) => setSoundsLikeYouCards(res.cards))
        .catch(() => setSoundsLikeYouCards([]));
      return result.memory_md;
    } finally {
      setIsFinishingRound(false);
    }
  };

  // 「new round」：把上一轮在提示词页面的所有残留全部清空，从零开始。
  const resetRound = () => {
    clearIdleTimer();
    setNotes([]);
    setExplanation("");
    setCard(null);
    setSessionId(null);
    setCards([]);
    setLikedCards([]);
    setIsLoadingCards(false);
    setIsBuilding(false);
    setCardsError("");
    setMemoryMd("");
    setSoundsLikeYouCards([]);
    setIsFinishingRound(false);
    setExplanationsByTrackId({});
  };

  const sendFeedback = async (
    trackId: string,
    verdict: "like" | "dislike",
    mode: FeedbackMode = "normal",
  ) => {
    if (!sessionId) return;
    if (verdict === "like") {
      const liked = cards.find(
        (card) => card.cyanite_id === trackId || card.track_id === trackId,
      );
      if (liked) {
        setLikedCards((prev) =>
          prev.some((card) => card.cyanite_id === liked.cyanite_id)
            ? prev
            : [...prev, liked],
        );
      }
    }
    const result = await feedback(sessionId, trackId, verdict, mode);
    setCards(result.cards);
    if (verdict === "dislike" || mode === "normal") {
      setExplanationsByTrackId((prev) => {
        const next = { ...prev };
        delete next[trackId];
        return next;
      });
    }
  };

  // 「听起来像你」逐张翻牌：喜欢就进 liked songs，翻到下一张；不喜欢直接翻下一张。
  // 翻完候选即止（不再补歌）。它不属于本轮 session，所以不打 /feedback。
  const advanceSoundsLikeYou = (cyaniteId: string) =>
    setSoundsLikeYouCards((prev) =>
      prev.filter((card) => card.cyanite_id !== cyaniteId),
    );

  const likeSoundsLikeYou = (card: RecommendationCard) => {
    setLikedCards((prev) =>
      prev.some((c) => c.cyanite_id === card.cyanite_id) ? prev : [...prev, card],
    );
    advanceSoundsLikeYou(card.cyanite_id);
  };

  const dismissSoundsLikeYou = (card: RecommendationCard) =>
    advanceSoundsLikeYou(card.cyanite_id);

  const unlikeTrack = (trackId: string) => {
    setLikedCards((prev) =>
      prev.filter(
        (card) => card.cyanite_id !== trackId && card.track_id !== trackId,
      ),
    );
  };

  const explainTrack = async (trackId: string) => {
    const cached = explanationsByTrackId[trackId];
    if (cached) return cached;
    if (!sessionId) throw new Error("No active session");
    const result = await explain(sessionId, trackId);
    setExplanationsByTrackId((prev) => ({ ...prev, [trackId]: result }));
    return result;
  };

  const explainSoundsLikeYouTrack = async (cyaniteId: string) => {
    const cached = explanationsByTrackId[`sly:${cyaniteId}`];
    if (cached) return cached;
    const result = await explainSoundsLikeYou("demo", cyaniteId);
    setExplanationsByTrackId((prev) => ({ ...prev, [`sly:${cyaniteId}`]: result }));
    return result;
  };

  const addNote = () => {
    setNotes((prev) =>
      prev.length >= MAX_NOTES
        ? prev
        : [
            ...prev,
            {
              id: crypto.randomUUID(),
              body: "",
              createdAt: new Date().toISOString(),
            },
          ],
    );
  };

  // Once a memo is committed (Enter) it can no longer be edited; new ideas go on a fresh memo.
  const lockNote = (id: string) => {
    setNotes((prev) =>
      prev.map((note) => (note.id === id ? { ...note, locked: true } : note)),
    );
  };

  const updateNote = (id: string, body: string) => {
    setNotes((prev) =>
      prev.map((note) => (note.id === id ? { ...note, body } : note)),
    );
    setSessionId(null);
    setCards([]);
    setLikedCards([]);
    setCardsError("");
    setExplanationsByTrackId({});
    // Finish editing if the user stops typing for 3 seconds.
    clearIdleTimer();
    idleTimer.current = window.setTimeout(() => {
      void finishEditing();
    }, 3000);
  };

  const value: NotesContextValue = {
    notes,
    explanation,
    card,
    sessionId,
    cards,
    likedCards,
    isLoadingCards,
    isBuilding,
    cardsError,
    memoryMd,
    soundsLikeYouCards,
    likeSoundsLikeYou,
    dismissSoundsLikeYou,
    isFinishingRound,
    resetRound,
    confirmSound,
    completeRound,
    sendFeedback,
    unlikeTrack,
    explainTrack,
    explainSoundsLikeYouTrack,
    explanationsByTrackId,
    addNote,
    updateNote,
    lockNote,
    finishEditing: () => void finishEditing(),
    buildPseudoExplanation,
  };

  return (
    <NotesContext.Provider value={value}>{children}</NotesContext.Provider>
  );
};

// eslint-disable-next-line react/only-export-components
export const useNotes = (): NotesContextValue => {
  const ctx = useContext(NotesContext);
  if (!ctx) {
    throw new Error("useNotes must be used within a NotesProvider");
  }
  return ctx;
};
