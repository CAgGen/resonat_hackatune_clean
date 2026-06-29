import { useEffect, useMemo, useRef, useState } from "react";
import { createPortal, flushSync } from "react-dom";
import { useNavigate } from "react-router-dom";
import GrainientBackground from "../components/GrainientBackground";
import MusicCard from "../components/MusicCard";
import NoteCard from "../components/NoteCard";
import PlaylistFan from "../components/PlaylistFan";
import Stack from "../components/Stack";
import TrackReasonModal from "../components/TrackReasonModal";
import Plus from "../components/icons/Plus";
import { useNotes } from "../context/NotesContext";
import { useAudioPlayer } from "../hooks/useAudioPlayer";
import { COVER_POOL, downloadUrl, trackUrl, type SampleTrack } from "../sampleTracks";
import type { FeedbackMode, RecommendationCard } from "../api";

const displayTitle = (card: RecommendationCard) =>
  card.title || (card.track_id ? `Track ${card.track_id}` : "Recommended track");

const displayArtist = (card: RecommendationCard) =>
  card.artist || "Unknown artist";

// djb2 hash — spreads ids across the full cover pool far better than summing
// char codes (which collided constantly).
const hashString = (value: string) => {
  let hash = 5381;
  for (let i = 0; i < value.length; i++) {
    hash = ((hash << 5) + hash + value.charCodeAt(i)) >>> 0;
  }
  return hash;
};

const coverForCard = (card: RecommendationCard) => {
  const id = card.cyanite_id || card.track_id || "";
  return COVER_POOL[hashString(id) % COVER_POOL.length];
};

const toTrack = (card: RecommendationCard): SampleTrack => ({
  id: card.cyanite_id,
  trackId: card.track_id,
  title: displayTitle(card),
  artist: displayArtist(card),
  url: card.track_id ? trackUrl(card.track_id) : "",
  cover: coverForCard(card),
  surprise: card.source === "surprise",
});

const LikedSongsShelf = ({
  tracks,
  onUnlike,
}: {
  tracks: SampleTrack[];
  onUnlike: (track: SampleTrack) => void;
}) => {
  const { playingId, play, stop } = useAudioPlayer(tracks);
  const [licenseTrackId, setLicenseTrackId] = useState<string | null>(null);

  return (
    <section className="mt-5 flex min-h-0 flex-1 flex-col rounded-[6px] border border-[var(--color-border)] bg-[rgba(229,225,214,.045)] p-3">
      <div className="flex shrink-0 items-center justify-between border-b border-[var(--color-border)] pb-3">
        <h3 className="font-display text-[14px] font-bold uppercase leading-none text-[var(--paper)] opacity-80">
          liked songs
        </h3>
        <span className="font-display text-[12px] font-bold leading-none text-[var(--paper)] opacity-45">
          {tracks.length}
        </span>
      </div>
      <div className="mt-3 flex min-h-[88px] flex-1 flex-col gap-2 overflow-y-auto pr-1">
        {tracks.length === 0 && (
          <p className="font-serif m-auto text-[13px] italic text-[var(--paper)] opacity-40">
            liked tracks land here
          </p>
        )}
        {tracks.map((track) => {
          const numericTrackId = (track.trackId ?? track.id).match(/^\d+$/)
            ? track.trackId ?? track.id
            : "";
          const isPlaying = playingId === track.id;
          return (
            <article
              key={track.id}
              className="grid grid-cols-[44px_1fr] gap-3 rounded-[6px] bg-[rgba(229,225,214,.07)] p-2"
            >
              <img
                src={track.cover}
                alt={`${track.title} cover art`}
                className="h-11 w-11 rounded-[4px] object-cover"
              />
              <div className="min-w-0">
                <p className="font-display truncate text-[13px] font-bold uppercase leading-tight text-[var(--paper)]">
                  {track.title}
                </p>
                <p className="font-serif truncate text-[12px] italic leading-tight text-[var(--paper)] opacity-60">
                  {track.artist}
                </p>
                <div className="mt-2 flex gap-2">
                  <button
                    type="button"
                    onClick={() => (isPlaying ? stop() : play(track.id))}
                    className="font-display inline-flex items-center rounded-full border border-[var(--paper)] px-2.5 py-1 text-[11px] font-bold uppercase leading-none text-[var(--paper)] transition-colors hover:border-[var(--yellow)] hover:bg-[var(--yellow)] hover:text-[var(--ink)]"
                  >
                    {isPlaying ? "stop" : "preview"}
                  </button>
                  {numericTrackId && (
                    <button
                      type="button"
                      onClick={() => setLicenseTrackId(numericTrackId)}
                      className="font-display inline-flex items-center rounded-full border border-[var(--paper)] px-6 py-1 text-[11px] font-bold uppercase leading-none text-[var(--paper)] transition-colors hover:border-[var(--yellow)] hover:bg-[var(--yellow)] hover:text-[var(--ink)]"
                    >
                      download
                    </button>
                  )}
                  <button
                    type="button"
                    onClick={() => {
                      if (isPlaying) stop();
                      onUnlike(track);
                    }}
                    className="font-display rounded-full border border-[var(--paper)] px-2.5 py-1 text-[11px] font-bold uppercase leading-none text-[var(--paper)] opacity-70 transition-colors hover:border-[var(--red)] hover:bg-[var(--red)] hover:text-[var(--paper)] hover:opacity-100"
                  >
                    unlike
                  </button>
                </div>
              </div>
            </article>
          );
        })}
      </div>
      {licenseTrackId &&
        createPortal(
          <div
            className="fixed inset-0 z-[20000] flex items-center justify-center bg-[rgba(27,27,27,.88)] p-6 backdrop-blur-sm"
            onClick={() => setLicenseTrackId(null)}
          >
            <section
              role="dialog"
              aria-modal="true"
              aria-labelledby="shelf-download-license-title"
              onClick={(event) => event.stopPropagation()}
              className="w-full max-w-md rounded-[10px] bg-[var(--paper)] p-8 text-[var(--ink)] shadow-[var(--shadow-block)]"
            >
              <h2
                id="shelf-download-license-title"
                className="font-display text-[28px] font-bold uppercase leading-none tracking-[-0.01em]"
              >
                Personal use only
              </h2>
              <p className="font-serif mt-5 text-[16px] leading-[1.6]">
                These tracks come from Jamendo under a Creative Commons license.
                You're free to download and enjoy them personally, but{" "}
                <strong>commercial use is not permitted</strong> without a
                separate license from Jamendo.
              </p>
              <div className="mt-7 flex items-center justify-end gap-3">
                <button
                  type="button"
                  onClick={() => setLicenseTrackId(null)}
                  className="font-display rounded-full px-5 py-2.5 text-[14px] font-bold uppercase opacity-60 transition hover:opacity-100"
                >
                  Cancel
                </button>
                <a
                  href={downloadUrl(licenseTrackId)}
                  download
                  onClick={() => setLicenseTrackId(null)}
                  className="font-display rounded-full border border-[var(--ink)] px-5 py-2.5 text-[14px] font-bold uppercase leading-none text-[var(--ink)] transition-colors hover:border-[var(--yellow)] hover:bg-[var(--yellow)] hover:text-[var(--ink)]"
                >
                  Download
                </a>
              </div>
            </section>
          </div>,
          document.body,
        )}
    </section>
  );
};

// Render memory.md in the page style without a markdown library: bounded scroll + wrapping,
// **x** as accent emphasis, and custom styles for ## / --- / _footnotes_ so raw markdown symbols do not leak.
const renderInline = (text: string) =>
  text.split(/(\*\*[^*]+\*\*)/g).map((part, i) =>
    /^\*\*[^*]+\*\*$/.test(part) ? (
      <strong key={i} className="font-bold text-[var(--yellow)]">
        {part.slice(2, -2)}
      </strong>
    ) : (
      <span key={i}>{part}</span>
    ),
  );

const MemoryProfile = ({ md }: { md: string }) => (
  <div className="mt-4 max-w-3xl rounded-[6px] border border-[var(--color-border)] bg-[rgba(229,225,214,.05)] p-5 [overflow-wrap:anywhere]">
    {md.split("\n").map((raw, i) => {
      const line = raw.trim();
      if (!line || /^#\s*memory\b/i.test(line)) return null;
      if (line === "---")
        return <hr key={i} className="my-4 border-[var(--color-border)]" />;
      if (line.startsWith("## "))
        return (
          <h3
            key={i}
            className="font-display mb-2 mt-1 text-[14px] font-bold uppercase tracking-[0.06em] text-[var(--paper)] opacity-70"
          >
            {line.slice(3)}
          </h3>
        );
      if (/^_.*_$/.test(line))
        return (
          <p
            key={i}
            className="font-serif mt-3 text-[12px] italic leading-[1.5] text-[var(--paper)] opacity-45"
          >
            {line.replace(/^_|_$/g, "")}
          </p>
        );
      if (/^\d+\.\s/.test(line))
        return (
          <p
            key={i}
            className="font-serif mt-1 text-[14px] leading-[1.6] text-[var(--paper)] opacity-80"
          >
            {renderInline(line)}
          </p>
        );
      return (
        <p
          key={i}
          className="font-serif mt-2 text-[16px] leading-[1.7] text-[var(--paper)] opacity-90"
        >
          {renderInline(line)}
        </p>
      );
    })}
  </div>
);

// Dedicated "sounds like you" card: same behavior as the five playlist cards: hover preview,
// open explanation, like into library, dismiss to flip to the next, and download. Consumes one by one until exhausted.
const SoundsLikeYouCard = ({
  card,
  modalOpen,
  onOpen,
  onLike,
  onDismiss,
}: {
  card: RecommendationCard;
  modalOpen: boolean;
  onOpen: () => void;
  onLike: () => void;
  onDismiss: () => void;
}) => {
  const track = useMemo(() => toTrack(card), [card]);
  const playerTracks = useMemo(() => [track], [track]);
  const { playingId, play, stop } = useAudioPlayer(playerTracks);
  const numericId = (track.trackId ?? track.id).match(/^\d+$/)
    ? track.trackId ?? track.id
    : "";

  return (
    <div
      onMouseEnter={() => play(track.id)}
      onMouseLeave={() => {
        // Opening the why-modal triggers mouseleave — keep playing then.
        if (!modalOpen) stop();
      }}
    >
      <MusicCard
        title={track.title}
        artist={track.artist}
        cover={track.cover}
        isPlaying={playingId === track.id}
        badge="✦ this is you"
        downloadUrl={numericId ? downloadUrl(numericId) : undefined}
        onOpen={() => {
          play(track.id);
          onOpen();
        }}
        onLike={(liked) => {
          if (liked) onLike();
        }}
        onDismiss={onDismiss}
      />
    </div>
  );
};

const ResultsPage = () => {
  const {
    notes,
    explanation,
    cards,
    likedCards,
    sendFeedback,
    unlikeTrack,
    explainTrack,
    explainSoundsLikeYouTrack,
    explanationsByTrackId,
    completeRound,
    memoryMd,
    soundsLikeYouCards,
    likeSoundsLikeYou,
    dismissSoundsLikeYou,
    isFinishingRound,
    resetRound,
  } = useNotes();
  const [isLeaving, setIsLeaving] = useState(false);
  const [feedbackMode, setFeedbackMode] = useState<FeedbackMode>("normal");
  const [slyModalOpen, setSlyModalOpen] = useState(false);
  const [slyLoading, setSlyLoading] = useState(false);
  const leaveTimer = useRef<number | null>(null);
  const navigate = useNavigate();
  const filledNotes = notes.filter((note) => note.body.trim());
  const antiAddiction = feedbackMode === "anti_addiction";

  useEffect(
    () => () => {
      if (leaveTimer.current !== null) {
        window.clearTimeout(leaveTimer.current);
      }
    },
    [],
  );

  // steer = go back to the taste board keeping this round's notes/likes so the
  // user can append more. new round = wipe everything and start fresh.
  const goToBoard = (reset: boolean) => {
    const run = () => {
      if (reset) resetRound();
      navigate("/");
    };
    if (!document.startViewTransition) {
      setIsLeaving(true);
      leaveTimer.current = window.setTimeout(run, 520);
      return;
    }
    document.startViewTransition(() => flushSync(run));
  };
  const handleSteer = () => goToBoard(false);
  const handleNewRound = () => goToBoard(true);

  // Assign covers deduped across the on-screen cards, so a replacement never
  // reuses a cover already showing (the pool is far larger than the visible
  // count). On a collision, probe forward through the pool for a free image.
  const tracks = useMemo(() => {
    const used = new Set<string>();
    return cards.map((card) => {
      const track = toTrack(card);
      let cover = track.cover;
      if (used.has(cover)) {
        const start = COVER_POOL.indexOf(cover);
        for (let k = 1; k < COVER_POOL.length; k++) {
          const candidate = COVER_POOL[(start + k) % COVER_POOL.length];
          if (!used.has(candidate)) {
            cover = candidate;
            break;
          }
        }
      }
      used.add(cover);
      return cover === track.cover ? track : { ...track, cover };
    });
  }, [cards]);

  const likedTracks = useMemo(() => likedCards.map(toTrack), [likedCards]);
  const likedTrackIds = useMemo(
    () => new Set(likedTracks.map((track) => track.id)),
    [likedTracks],
  );

  // Consume one by one: the current card is always the first candidate in the queue.
  const slyCard = soundsLikeYouCards[0] ?? null;
  const slyTrack = useMemo(
    () => (slyCard ? toTrack(slyCard) : null),
    [slyCard],
  );
  const slyExplanation = slyCard
    ? explanationsByTrackId[`sly:${slyCard.cyanite_id}`]
    : undefined;

  const openSlyModal = async () => {
    if (!slyCard) return;
    setSlyModalOpen(true);
    if (slyExplanation) return;
    setSlyLoading(true);
    try {
      await explainSoundsLikeYouTrack(slyCard.cyanite_id);
    } catch {
      // Explanation failed: keep modal open and let TrackReasonModal fall back to empty text.
    } finally {
      setSlyLoading(false);
    }
  };

  // Auto-prefetch explanations serially (one finishes before the next; no fan-out) and do not
  // auto-retry after an attempt (track success/failure). Otherwise failed tracks would be resent
  // by the effect repeatedly and drive OpenAI into 429. Manual retry goes through card onExplain.
  const attemptedRef = useRef<Set<string>>(new Set());
  useEffect(() => {
    let cancelled = false;
    void (async () => {
      for (const track of tracks) {
        if (cancelled) return;
        if (explanationsByTrackId[track.id] || attemptedRef.current.has(track.id)) continue;
        attemptedRef.current.add(track.id);
        await explainTrack(track.id).catch(() => undefined);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [explainTrack, explanationsByTrackId, tracks]);

  return (
    <main
      className={`results-page-enter relative isolate flex min-h-screen w-full flex-col overflow-x-hidden bg-[var(--ink)] text-[var(--paper)] md:h-screen md:flex-row md:overflow-hidden ${
        isLeaving ? "results-page-leaving" : ""
      }`}
    >
      <GrainientBackground />

      {/* Left panel — the shrunk taste board. */}
      <aside className="relative z-10 flex w-full shrink-0 flex-col overflow-y-auto border-b border-[var(--color-border)] p-5 md:h-screen md:w-[28rem] md:overflow-y-auto md:border-b-0 md:border-r">
        <section className="shrink-0 border-b border-[var(--color-border)] pb-8">
          <h2 className="font-display mb-5 text-[24px] font-bold uppercase leading-none text-[var(--paper)]">
            Your taste board
          </h2>

          {/* Draggable-free card stack of the brief's memos (click to cycle). */}
          {filledNotes.length > 0 && (
            <div className="mx-auto mb-2 mt-2 h-[200px] w-full max-w-[280px]">
              <Stack
                randomRotation
                sendToBackOnClick
                cards={filledNotes.map((note, index) => (
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
        </section>

        <LikedSongsShelf tracks={likedTracks} onUnlike={(track) => unlikeTrack(track.id)} />

        {/* "steer…" — go back to the start page to refine the board. */}
        <button
          type="button"
          onClick={handleSteer}
          disabled={isLeaving}
          className="steer-button font-display mt-3 flex min-h-11 w-full shrink-0 items-center gap-2 rounded-full border-[2.5px] border-solid border-[var(--paper)] px-5 py-3 text-left text-[16px] font-bold uppercase leading-[1.4] text-[var(--paper)] transition-colors hover:border-[var(--yellow)] hover:bg-[var(--yellow)] hover:text-[var(--ink)] disabled:cursor-default"
        >
          <Plus size={18} />
          <span>steer...</span>
        </button>
      </aside>

      {/* Right panel — the playlist. */}
      <section className="relative z-10 w-full flex-1 overflow-y-auto p-6 md:p-10">
        <div className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
          <h1 className="font-display max-w-3xl text-[28px] font-bold uppercase leading-none tracking-[-0.01em] text-[var(--paper)]">
            A playlist built from your memo
          </h1>
          <div className="flex w-fit items-center gap-3">
            <button
              type="button"
              aria-pressed={antiAddiction}
              onClick={() =>
                setFeedbackMode((mode) =>
                  mode === "anti_addiction" ? "normal" : "anti_addiction",
                )
              }
              className="font-display w-fit rounded-full border-[2.5px] border-solid border-[var(--paper)] px-4 py-2 text-[13px] font-bold uppercase leading-none text-[var(--paper)] transition-colors hover:border-[var(--yellow)] hover:bg-[var(--yellow)] hover:text-[var(--ink)]"
              style={{
                background: antiAddiction ? "var(--yellow)" : undefined,
                borderColor: antiAddiction ? "var(--yellow)" : undefined,
                color: antiAddiction ? "var(--ink)" : undefined,
              }}
            >
              anti-addiction {antiAddiction ? "on" : "off"}
            </button>
            {/* Start a new round and return to the taste board. */}
            <button
              type="button"
              onClick={handleNewRound}
              disabled={isLeaving}
              className="font-display w-fit rounded-full border-[2.5px] border-solid border-[var(--paper)] px-4 py-2 text-[13px] font-bold uppercase leading-none text-[var(--paper)] transition-colors hover:border-[var(--yellow)] hover:bg-[var(--yellow)] hover:text-[var(--ink)] disabled:cursor-default"
            >
              new round
            </button>
          </div>
        </div>

        <div className="mt-8">
          {tracks.length > 0 ? (
            <PlaylistFan
              tracks={tracks}
              antiAddiction={antiAddiction}
              likedIds={likedTrackIds}
              onLike={(track) => sendFeedback(track.id, "like", feedbackMode)}
              onUnlike={(track) => unlikeTrack(track.id)}
              onDismiss={(track) => sendFeedback(track.id, "dislike", feedbackMode)}
              onExplain={(track) => explainTrack(track.id)}
            />
          ) : (
            <p className="font-serif text-[24px] italic text-[var(--paper)] opacity-80">
              No recommendations loaded yet. Steer back and find your sound again.
            </p>
          )}
        </div>

        {explanation && (
          <p className="font-serif mt-8 max-w-3xl text-[22px] italic leading-[1.25] text-[var(--paper)]">
            {explanation}
          </p>
        )}

        {/* "Finish this round" persists this round's selected songs as feeling memory. */}
        {tracks.length > 0 && (
          <button
            type="button"
            onClick={() => void completeRound()}
            disabled={isFinishingRound}
            className="font-display mt-10 flex min-h-11 items-center gap-2 rounded-full border-[2.5px] border-solid border-[var(--paper)] px-6 py-3 text-[16px] font-bold uppercase leading-[1.4] text-[var(--paper)] transition-colors hover:border-[var(--yellow)] hover:bg-[var(--yellow)] hover:text-[var(--ink)] disabled:opacity-60"
          >
            {isFinishingRound ? "saving your feel..." : "Finish this Round · save my feel"}
          </button>
        )}

        {memoryMd && (
          <div className="mt-6">
            <h2 className="font-display text-[20px] font-bold uppercase leading-none text-[var(--paper)]">
              your feel, learned
            </h2>
            {/* Profile on the left; dedicated "sounds like you" card on the right (stacked on narrow screens). */}
            <div className="mt-4 flex flex-col gap-6 lg:flex-row lg:items-start">
              <div className="min-w-0 lg:flex-1">
                <MemoryProfile md={memoryMd} />
              </div>
              {slyCard && (
                <div className="w-full shrink-0 lg:w-60">
                  <p className="font-display mb-2 text-[12px] font-bold uppercase tracking-[0.06em] text-[var(--yellow)]">
                    sounds like you
                  </p>
                  {/* Same behavior as the five cards above: hover preview / open explanation / like / dismiss to next / download. */}
                  <SoundsLikeYouCard
                    key={slyCard.cyanite_id}
                    card={slyCard}
                    modalOpen={slyModalOpen}
                    onOpen={() => void openSlyModal()}
                    onLike={() => likeSoundsLikeYou(slyCard)}
                    onDismiss={() => dismissSoundsLikeYou(slyCard)}
                  />
                </div>
              )}
            </div>
          </div>
        )}
      </section>

      {slyModalOpen && slyTrack && (
        <TrackReasonModal
          track={{ track: slyTrack.title, artist: slyTrack.artist, cover: slyTrack.cover }}
          reasonText={slyExplanation?.why_text ?? ""}
          isLoading={slyLoading && !slyExplanation}
          title="why this sounds like you"
          onClose={() => setSlyModalOpen(false)}
        />
      )}
    </main>
  );
};

export default ResultsPage;
