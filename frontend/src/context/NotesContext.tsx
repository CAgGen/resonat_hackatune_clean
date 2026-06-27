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
    setExplanation(buildPseudoExplanation(notesRef.current));
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
