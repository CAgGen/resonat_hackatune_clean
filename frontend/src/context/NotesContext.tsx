import {
  createContext,
  useContext,
  useEffect,
  useRef,
  useState,
} from "react";
import type { ReactNode } from "react";
import type { Note } from "../types";
import type { QueryCard } from "../api";
import { intent } from "../api";

const joinNotes = (notes: Note[]): string =>
  notes
    .map((note) => note.body.trim())
    .filter(Boolean)
    .join("; ");

// Placeholder "sound briefs" for front-end testing while the backend (/intent)
// isn't wired up. A random one is shown each time editing finishes.
const PSEUDO_EXPLANATIONS = [
  "A warm, relaxed summer-evening playlist, calm, chilled, flowing and acoustic, with low-medium energy to cool you down without feeling sleepy.",
  "A cozy late-night wind-down set, soft, intimate and acoustic, with gentle low energy to help you unwind without drifting off.",
  "An upbeat sunny-morning mix, bright, breezy and rhythmic, with medium-high energy to get you moving.",
  "A focused deep-work soundtrack, steady, minimal and atmospheric, with calm mid energy to keep you in flow.",
  "A nostalgic rainy-day playlist, mellow, warm and a little melancholic, with soft low energy and plenty of space.",
];

// Local fallback used when the backend (/intent) isn't reachable, so the
// front end stays testable on its own.
const buildPseudoExplanation = (notes: Note[]): string => {
  if (!joinNotes(notes)) return "";
  const index = Math.floor(Math.random() * PSEUDO_EXPLANATIONS.length);
  return PSEUDO_EXPLANATIONS[index];
};

interface NotesContextValue {
  notes: Note[];
  explanation: string;
  card: QueryCard | null;
  addNote: () => void;
  updateNote: (id: string, body: string) => void;
  finishEditing: () => void;
  buildPseudoExplanation: (notes: Note[]) => string;
}

const NotesContext = createContext<NotesContextValue | null>(null);

export const NotesProvider = ({ children }: { children: ReactNode }) => {
  const [notes, setNotes] = useState<Note[]>([]);
  const [explanation, setExplanation] = useState("");
  const [card, setCard] = useState<QueryCard | null>(null);

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

  // "Finish edit": compile the post-its into an explanation via /intent,
  // falling back to a local pseudo explanation when the backend is offline.
  const finishEditing = async () => {
    clearIdleTimer();
    const text = joinNotes(notesRef.current);
    if (!text) {
      setCard(null);
      setExplanation("");
      return;
    }
    try {
      const result = await intent(text);
      setCard(result);
      setExplanation(result.interpretation_plain);
    } catch {
      // Backend not running — show the local pseudo explanation instead.
      setCard(null);
      setExplanation(buildPseudoExplanation(notesRef.current));
    }
  };

  const addNote = () => {
    setNotes((prev) => [...prev, { id: crypto.randomUUID(), body: "" }]);
  };

  const updateNote = (id: string, body: string) => {
    setNotes((prev) =>
      prev.map((note) => (note.id === id ? { ...note, body } : note)),
    );
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
    addNote,
    updateNote,
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
