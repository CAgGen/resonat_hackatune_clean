import { useEffect, useRef, useState } from "react";
import { flushSync } from "react-dom";
import { useNavigate } from "react-router-dom";
import Canvas from "../components/Canvas";
import AddNoteButton from "../components/AddNoteButton";
import NoteCard from "../components/NoteCard";
import Slogan from "../components/Slogan";
import { useNotes } from "../context/NotesContext";

const GREETING = "Hey, what should today sound like?";

const StartPage = () => {
  const {
    notes,
    explanation,
    addNote,
    updateNote,
    finishEditing,
    confirmSound,
    isLoadingCards,
  } = useNotes();
  const [toast, setToast] = useState<string | null>(null);
  const [isLeaving, setIsLeaving] = useState(false);
  const leaveTimer = useRef<number | null>(null);
  const navigate = useNavigate();

  const isEmpty = notes.length === 0;
  const hasValidPostIt = notes.some((note) => note.body.trim());

  const showToast = (message: string) => {
    setToast(message);
    window.setTimeout(() => setToast(null), 2500);
  };

  useEffect(
    () => () => {
      if (leaveTimer.current !== null) {
        window.clearTimeout(leaveTimer.current);
      }
    },
    [],
  );

  const handleFindMySound = async () => {
    if (!hasValidPostIt) {
      showToast("Add a note first to describe the music you want.");
      return;
    }
    const hasCards = await confirmSound();
    if (!hasCards) {
      showToast("I couldn't find tracks yet. Try again in a moment.");
      return;
    }
    if (!document.startViewTransition) {
      setIsLeaving(true);
      leaveTimer.current = window.setTimeout(() => {
        navigate("/results");
      }, 900);
      return;
    }

    document.startViewTransition(() => {
      flushSync(() => navigate("/results"));
    });
  };

  return (
    <main
      className={`start-page-transition relative min-h-screen w-full ${
        isLeaving ? "start-page-transitioning" : ""
      }`}
    >
      <Canvas>
        <div className="start-page-content flex min-h-screen flex-col items-center justify-center gap-10 p-12">
          {/* Center text: greeting at the start, the explanation once editing finishes. */}
          {explanation ? (
            <div className="start-page-copy max-w-2xl text-center">
              <p className="font-sans mb-3 -rotate-2 text-[28px] font-semibold leading-none text-[var(--red)]">
                We translated your note into a sound brief.
              </p>
              <p className="font-serif text-[32px] italic leading-[1.2] text-[var(--paper)]">
                {explanation}
              </p>
            </div>
          ) : (
            <h1
              aria-label={GREETING}
              className="font-display start-page-copy min-w-0 px-4 text-center text-[28px] font-bold uppercase leading-none tracking-[-0.01em] text-[var(--paper)] sm:text-[48px] lg:text-[56px]"
            >
              <span className="block">Hey,</span>
              <span className="block">what should today sound like?</span>
            </h1>
          )}

          {/* Starting state: add button centered beneath the greeting. */}
          {isEmpty && <AddNoteButton onClick={addNote} />}

          {/* Notes cluster — centered, wrapping. The add button sits in the
              next post-it's slot, not off in a sidebar. */}
          {!isEmpty && (
            <div className="flex max-w-5xl flex-wrap items-start justify-center gap-8">
              {notes.map((note, index) => (
                <NoteCard
                  key={note.id}
                  note={note}
                  index={index}
                  onChange={updateNote}
                  onFinishEdit={finishEditing}
                  viewTransitionName={`note-${note.id}`}
                />
              ))}
              <div className="flex min-h-[150px] w-80 items-center justify-center">
                <AddNoteButton onClick={addNote} />
              </div>
            </div>
          )}
        </div>
      </Canvas>

      <Slogan />

      {hasValidPostIt && (
        <button
          type="button"
          onClick={handleFindMySound}
          disabled={isLeaving || isLoadingCards}
          className="font-display find-sound-button fixed bottom-6 right-6 z-[10000] -rotate-3 rounded-full bg-[var(--yellow)] px-6 py-3 text-[16px] font-bold uppercase leading-[1.4] text-[var(--ink)] shadow-[var(--shadow-block)] transition duration-150 hover:rotate-0 hover:bg-[var(--red)] hover:text-[var(--paper)] disabled:cursor-default"
        >
          {isLoadingCards ? "Finding..." : "Find my sound"}
        </button>
      )}

      {toast && (
        <div
          role="status"
          className="font-serif fixed bottom-24 right-6 z-[10000] rounded-[10px] bg-[var(--paper)] px-4 py-2 text-[18px] leading-[1.4] text-[var(--ink)] shadow-[var(--shadow-block)]"
        >
          {toast}
        </div>
      )}
    </main>
  );
};

export default StartPage;
