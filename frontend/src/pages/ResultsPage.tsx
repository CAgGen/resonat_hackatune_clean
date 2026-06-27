import { useNavigate } from "react-router-dom";
import NoteCard from "../components/NoteCard";
import PlaylistFan from "../components/PlaylistFan";
import Stack from "../components/Stack";
import Plus from "../components/icons/Plus";
import { useNotes } from "../context/NotesContext";

// Temporary static playlist title — will come from the backend later.
const PLAYLIST_TITLE = "Summer Relaxation: Cooling Vibes with Harry Styles and Friends";

const ResultsPage = () => {
  const { notes } = useNotes();
  const navigate = useNavigate();

  return (
    <main className="flex min-h-screen w-full bg-[#1a1b20]">
      {/* Left panel — the shrunk taste board. */}
      <aside className="canvas-grid flex h-screen w-96 shrink-0 flex-col overflow-y-auto border-r border-black/40 p-5">
        <h2 className="mb-5 text-lg font-semibold text-white/85">
          Your taste board
        </h2>

        {/* Drag-free card stack of the brief's post-its (click to cycle). */}
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
                />
              ))}
            />
          </div>
        )}

        {/* "steer…" — go back to the start page to refine the board. */}
        <button
          type="button"
          onClick={() => navigate("/")}
          className="mt-6 flex w-full items-center gap-2 rounded-md border border-dashed border-white/20 px-4 py-3 text-left text-white/40 transition-colors hover:border-white/40 hover:text-white/70"
        >
          <Plus size={18} />
          <span className="text-sm">steer…</span>
        </button>
      </aside>

      {/* Right panel — the playlist. */}
      <section className="flex-1 overflow-y-auto p-10">
        <h1 className="text-2xl font-semibold text-white/90">
          A playlist built from your memo
        </h1>

        <p className="mt-6 text-xl font-medium text-indigo-300/90">
          {PLAYLIST_TITLE}
        </p>

        <div className="mt-12">
          <PlaylistFan />
        </div>
      </section>
    </main>
  );
};

export default ResultsPage;
