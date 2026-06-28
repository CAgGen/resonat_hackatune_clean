import { useEffect, useRef, useState } from "react";
import { flushSync } from "react-dom";
import { useNavigate } from "react-router-dom";
import Canvas from "../components/Canvas";
import AddNoteButton from "../components/AddNoteButton";
import NoteCard from "../components/NoteCard";
import Slogan from "../components/Slogan";
import { useNotes } from "../context/NotesContext";

const GREETING = "Hey, what should today sound like?";
const MAX_MEMOS = 6;

const StartPage = () => {
  const {
    notes,
    explanation,
    addNote,
    updateNote,
    lockNote,
    finishEditing,
    confirmSound,
    isLoadingCards,
    isBuilding,
    cardsError,
  } = useNotes();
  const [toast, setToast] = useState<string | null>(null);
  const [isLeaving, setIsLeaving] = useState(false);
  const leaveTimer = useRef<number | null>(null);
  const navigate = useNavigate();

  const isEmpty = notes.length === 0;
  const hasValidMemo = notes.some((note) => note.body.trim());
  const hasExplanation = Boolean(explanation.trim());
  const canAddMemo = notes.length < MAX_MEMOS;

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
    if (!hasValidMemo) {
      showToast("Add a memo first to describe the music you want.");
      return;
    }
    let hasCards = false;
    try {
      hasCards = await confirmSound();
    } catch (error) {
      showToast(error instanceof Error ? error.message : "I couldn't find tracks yet. Try again in a moment.");
      return;
    }
    if (!hasCards) {
      showToast(cardsError || "I couldn't find tracks yet. Try again in a moment.");
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

  const handleAddMemo = () => {
    if (!canAddMemo) {
      showToast("You can add up to 6 memos.");
      return;
    }
    addNote();
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
              <p className="font-sans mb-3 whitespace-nowrap text-[28px] font-semibold leading-none text-[var(--paper)]">
                We translated your memo into a sound brief.
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

          {hasExplanation && (
            <button
              type="button"
              onClick={handleFindMySound}
              disabled={isLeaving || isLoadingCards}
              className="font-display find-sound-button inline-flex items-center -rotate-3 rounded-full bg-[var(--yellow)] px-6 py-3 text-[16px] font-bold uppercase leading-[1.4] text-[var(--ink)] shadow-[var(--shadow-block)] transition duration-150 hover:rotate-0 hover:bg-[var(--red)] hover:text-[var(--paper)] disabled:cursor-default"
            >
              {isLoadingCards ? (
                <>
                  Finding your sound
                  <span className="ml-2 flex gap-1">
                    <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-current [animation-delay:-0.3s]" />
                    <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-current [animation-delay:-0.15s]" />
                    <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-current" />
                  </span>
                </>
              ) : (
                "Find my sound"
              )}
            </button>
          )}

          {/* Starting state: add memo centered beneath the greeting. */}
          {isEmpty && <AddNoteButton onClick={handleAddMemo} />}

          {/* Notes cluster — centered, wrapping. Add another memo beside the
              last visible memo. */}
          {!isEmpty && (
            <div className="flex max-w-5xl flex-wrap items-start justify-center gap-8">
              {notes.map((note, index) => {
                const isLatestMemo = index === notes.length - 1;
                const noteCard = (
                  <NoteCard
                    note={note}
                    index={index}
                    onChange={updateNote}
                    onFinishEdit={finishEditing}
                    onCommit={lockNote}
                    readOnly={!!note.locked}
                    viewTransitionName={`note-${note.id}`}
                  />
                );

                if (!isLatestMemo) {
                  return <div key={note.id}>{noteCard}</div>;
                }

                return (
                  <div
                    key={note.id}
                    className="relative flex h-[260px] w-[260px] items-center justify-center"
                  >
                    {noteCard}
                    {canAddMemo && (
                      <div
                        className="absolute left-[calc(100%+12px)] top-1/2 z-20 -translate-y-1/2"
                      >
                        <AddNoteButton onClick={handleAddMemo} />
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}

          {/* Building the sound brief: a typewriter line beneath the memos —
              same mono + blinking block caret as a memo, covers nothing. */}
          {isBuilding && (
            <div
              role="status"
              className="font-display text-[14px] font-bold uppercase tracking-[0.18em] text-[var(--paper)] opacity-80"
            >
              <span className="memo-typed">generating sound brief</span>
            </div>
          )}
        </div>
      </Canvas>

      <Slogan />

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
