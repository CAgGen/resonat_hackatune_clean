import { useEffect, useRef, useState } from "react";
import { flushSync } from "react-dom";
import { useNavigate } from "react-router-dom";
import GrainientBackground from "../components/GrainientBackground";
import NoteCard from "../components/NoteCard";
import PlaylistFan from "../components/PlaylistFan";
import Stack from "../components/Stack";
import Plus from "../components/icons/Plus";
import { useNotes } from "../context/NotesContext";

// Temporary static playlist title — will come from the backend later.
const PLAYLIST_TITLE = "Summer Relaxation: Cooling Vibes with Harry Styles and Friends";

const ResultsPage = () => {
  const { notes } = useNotes();
  const [isLeaving, setIsLeaving] = useState(false);
  const leaveTimer = useRef<number | null>(null);
  const navigate = useNavigate();

  useEffect(
    () => () => {
      if (leaveTimer.current !== null) {
        window.clearTimeout(leaveTimer.current);
      }
    },
    [],
  );

  const handleSteer = () => {
    if (!document.startViewTransition) {
      setIsLeaving(true);
      leaveTimer.current = window.setTimeout(() => {
        navigate("/");
      }, 520);
      return;
    }

    document.startViewTransition(() => {
      flushSync(() => navigate("/"));
    });
  };

  return (
    <main
      className={`results-page-enter relative isolate flex min-h-screen w-full flex-col overflow-x-hidden bg-[var(--ink)] text-[var(--paper)] md:flex-row md:overflow-hidden ${
        isLeaving ? "results-page-leaving" : ""
      }`}
    >
      <GrainientBackground />

      {/* Left panel — the shrunk taste board. */}
      <aside className="relative z-10 flex w-full shrink-0 flex-col overflow-y-auto border-b border-[var(--color-border)] p-5 md:h-screen md:w-96 md:border-b-0 md:border-r">
        <h2 className="font-display mb-5 text-[24px] font-bold uppercase leading-none text-[var(--paper)]">
          Your taste board
        </h2>

        {/* Draggable-free card stack of the brief's post-its (click to cycle). */}
        {notes.length > 0 && (
          <div className="mx-auto h-[210px] w-full max-w-[280px]">
            <Stack
              randomRotation
              sendToBackOnClick
              cards={notes.map((note, index) => (
                <NoteCard
                  key={note.id}
                  note={note}
                  index={index}
                  widthClass="w-full"
                  fill
                  readOnly
                  viewTransitionName={`note-${note.id}`}
                />
              ))}
            />
          </div>
        )}

        {/* "steer…" — go back to the start page to refine the board. */}
        <button
          type="button"
          onClick={handleSteer}
          disabled={isLeaving}
          className="steer-button font-display mt-6 flex min-h-11 w-full items-center gap-2 rounded-full border-[2.5px] border-solid border-[var(--paper)] px-5 py-3 text-left text-[16px] font-bold uppercase leading-[1.4] text-[var(--paper)] transition-colors hover:border-[var(--yellow)] hover:bg-[var(--yellow)] hover:text-[var(--ink)] disabled:cursor-default"
        >
          <Plus size={18} />
          <span>steer...</span>
        </button>
      </aside>

      {/* Right panel — the playlist. */}
      <section className="relative z-10 w-full flex-1 overflow-y-auto p-6 md:p-10">
        <h1 className="font-display max-w-3xl text-[40px] font-bold uppercase leading-none tracking-[-0.01em] text-[var(--paper)]">
          A playlist built from your memo
        </h1>

        <p className="font-serif mt-6 max-w-3xl text-[32px] italic leading-[1.2] text-[var(--yellow)]">
          {PLAYLIST_TITLE}
        </p>

        <div className="mt-10">
          <PlaylistFan />
        </div>
      </section>
    </main>
  );
};

export default ResultsPage;
