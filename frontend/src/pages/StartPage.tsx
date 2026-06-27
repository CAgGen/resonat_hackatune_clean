import { useState } from "react";
import { useNavigate } from "react-router-dom";
import Canvas from "../components/Canvas";
import Controls from "../components/Controls";
import NoteCard from "../components/NoteCard";
import Slogan from "../components/Slogan";
import Plus from "../components/icons/Plus";
import { useNotes } from "../context/NotesContext";

const GREETING = "Hi, What should today sound like?";

const StartPage = () => {
  const { notes, explanation, addNote, updateNote, finishEditing } = useNotes();
  const [toast, setToast] = useState<string | null>(null);
  const navigate = useNavigate();

  const isEmpty = notes.length === 0;

  const showToast = (message: string) => {
    setToast(message);
    window.setTimeout(() => setToast(null), 2500);
  };

  const handleFindMySound = () => {
    const hasContent = notes.some((note) => note.body.trim());
    if (!hasContent) {
      showToast("Add a note first to describe the music you want.");
      return;
    }
    navigate("/results");
  };

  return (
    <main className="relative min-h-screen w-full">
      <Canvas>
        <div className="flex min-h-screen flex-col items-center justify-center gap-10 p-12">
          {/* Center text: greeting at the start, the explanation once editing finishes. */}
          {explanation ? (
            <div className="max-w-2xl text-center">
              <p className="mb-2 text-sm font-semibold text-indigo-300/80">
                We translated your note into a sound brief.
              </p>
              <p className="text-lg leading-relaxed text-white/80">
                {explanation}
              </p>
            </div>
          ) : (
            <h1 className="max-w-2xl text-center text-3xl font-medium text-white/85 sm:text-4xl">
              {GREETING}
            </h1>
          )}

          {/* Notes cluster — centered, wrapping, non-overlapping. */}
          {!isEmpty && (
            <div className="flex max-w-5xl flex-wrap items-start justify-center gap-8">
              {notes.map((note, index) => (
                <NoteCard
                  key={note.id}
                  note={note}
                  index={index}
                  onChange={updateNote}
                  onFinishEdit={finishEditing}
                />
              ))}
            </div>
          )}

          {/* Starting state: add button centered beneath the greeting. */}
          {isEmpty && (
            <button
              type="button"
              onClick={addNote}
              aria-label="Add a note"
              title="Add a note"
              className="flex h-16 w-16 items-center justify-center rounded-full bg-[#35363e] text-white/90 shadow-lg transition-transform duration-300 hover:scale-110 hover:text-white"
            >
              <Plus size={30} />
            </button>
          )}
        </div>
      </Canvas>

      <Slogan />

      {/* Once notes exist, the add button lives in the left sidebar. */}
      {!isEmpty && <Controls onAdd={addNote} />}

      <button
        type="button"
        onClick={handleFindMySound}
        className="fixed bottom-6 right-6 z-[10000] rounded-full bg-indigo-500 px-6 py-3 text-base font-semibold text-white shadow-lg transition-colors hover:bg-indigo-400"
      >
        Find my sound →
      </button>

      {toast && (
        <div
          role="status"
          className="fixed bottom-24 right-6 z-[10000] rounded-lg bg-[#35363e] px-4 py-2 text-sm text-white/90 shadow-lg"
        >
          {toast}
        </div>
      )}
    </main>
  );
};

export default StartPage;
