import { useEffect, useMemo, useRef, useState } from "react";
import { flushSync } from "react-dom";
import { useNavigate } from "react-router-dom";
import GrainientBackground from "../components/GrainientBackground";
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

  return (
    <section className="mt-5 flex min-h-0 flex-col rounded-[6px] border border-[var(--color-border)] bg-[rgba(229,225,214,.045)] p-3 md:flex-1">
      <div className="flex shrink-0 items-center justify-between border-b border-[var(--color-border)] pb-3">
        <h3 className="font-display text-[14px] font-bold uppercase leading-none text-[var(--paper)] opacity-80">
          liked songs
        </h3>
        <span className="font-display text-[12px] font-bold leading-none text-[var(--paper)] opacity-45">
          {tracks.length}
        </span>
      </div>
      <div className="mt-3 flex max-h-64 min-h-[88px] flex-col gap-2 overflow-y-auto pr-1 md:max-h-none">
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
                    className="font-display rounded-full border border-[var(--paper)] px-2.5 py-1 text-[11px] font-bold uppercase leading-none text-[var(--paper)] transition-colors hover:border-[var(--yellow)] hover:bg-[var(--yellow)] hover:text-[var(--ink)]"
                  >
                    {isPlaying ? "stop" : "preview"}
                  </button>
                  {numericTrackId && (
                    <a
                      href={downloadUrl(numericTrackId)}
                      download
                      className="font-display inline-flex items-center rounded-full border border-[var(--paper)] px-2.5 py-1 text-[11px] font-bold uppercase leading-none text-[var(--paper)] transition-colors hover:border-[var(--yellow)] hover:bg-[var(--yellow)] hover:text-[var(--ink)]"
                    >
                      download
                    </a>
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
    </section>
  );
};

// 把 memory.md 渲染成与页面一致的样式（不引 markdown 库）：限高可滚动 + 自动换行，
// **x** 高亮为强调色，##／---／_脚注_ 各自成样式——不再露出原始 markdown 符号。
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
  <div className="mt-4 max-h-[55vh] max-w-3xl overflow-y-auto rounded-[6px] border border-[var(--color-border)] bg-[rgba(229,225,214,.05)] p-5 [overflow-wrap:anywhere]">
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
    soundsLikeYouCard,
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

  const handleSteer = () => {
    if (!document.startViewTransition) {
      setIsLeaving(true);
      leaveTimer.current = window.setTimeout(() => {
        resetRound();
        navigate("/");
      }, 520);
      return;
    }

    document.startViewTransition(() => {
      flushSync(() => {
        resetRound();
        navigate("/");
      });
    });
  };

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

  const slyTrack = useMemo(
    () => (soundsLikeYouCard ? toTrack(soundsLikeYouCard) : null),
    [soundsLikeYouCard],
  );
  const slyExplanation = soundsLikeYouCard
    ? explanationsByTrackId[`sly:${soundsLikeYouCard.cyanite_id}`]
    : undefined;

  const openSlyModal = async () => {
    if (!soundsLikeYouCard) return;
    setSlyModalOpen(true);
    if (slyExplanation) return;
    setSlyLoading(true);
    try {
      await explainSoundsLikeYouTrack(soundsLikeYouCard.cyanite_id);
    } catch {
      // 解释失败：modal 仍开着，TrackReasonModal 退到空文本。
    } finally {
      setSlyLoading(false);
    }
  };

  // 自动预取解释：串行（一个完成再下一个，不齐发）+ 试过就不再自动重试（成败都记），
  // 否则失败的 track 会被 effect 反复重发，把 OpenAI 打到 429。手动重试走卡片的 onExplain。
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
      className={`results-page-enter relative isolate flex min-h-screen w-full flex-col overflow-x-hidden bg-[var(--ink)] text-[var(--paper)] md:flex-row md:overflow-hidden ${
        isLeaving ? "results-page-leaving" : ""
      }`}
    >
      <GrainientBackground />

      {/* Left panel — the shrunk taste board. */}
      <aside className="relative z-10 flex w-full shrink-0 flex-col overflow-y-auto border-b border-[var(--color-border)] p-5 md:h-screen md:w-96 md:overflow-hidden md:border-b-0 md:border-r">
        <section className="shrink-0 border-b border-[var(--color-border)] pb-6">
          <h2 className="font-display mb-5 text-[24px] font-bold uppercase leading-none text-[var(--paper)]">
            Your taste board
          </h2>

          {/* Draggable-free card stack of the brief's memos (click to cycle). */}
          {filledNotes.length > 0 && (
            <div className="mx-auto h-[210px] w-full max-w-[280px]">
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
          className="steer-button font-display mt-5 flex min-h-11 w-full shrink-0 items-center gap-2 rounded-full border-[2.5px] border-solid border-[var(--paper)] px-5 py-3 text-left text-[16px] font-bold uppercase leading-[1.4] text-[var(--paper)] transition-colors hover:border-[var(--yellow)] hover:bg-[var(--yellow)] hover:text-[var(--ink)] disabled:cursor-default"
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
            {/* 开启新的一轮（回到 taste board）。 */}
            <button
              type="button"
              onClick={handleSteer}
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
              onExplain={async (track) => {
                const result = await explainTrack(track.id);
                return result.why_text;
              }}
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

        {/* 「完成本轮」— 把这一轮选的歌落成「感觉」记忆。 */}
        {tracks.length > 0 && (
          <button
            type="button"
            onClick={() => void completeRound()}
            disabled={isFinishingRound}
            className="font-display mt-10 flex min-h-11 items-center gap-2 rounded-full border-[2.5px] border-solid border-[var(--paper)] px-6 py-3 text-[16px] font-bold uppercase leading-[1.4] text-[var(--paper)] transition-colors hover:border-[var(--yellow)] hover:bg-[var(--yellow)] hover:text-[var(--ink)] disabled:opacity-60"
          >
            {isFinishingRound ? "saving your feel..." : "完成本轮 · save my feel"}
          </button>
        )}

        {memoryMd && (
          <div className="mt-6">
            <h2 className="font-display text-[20px] font-bold uppercase leading-none text-[var(--paper)]">
              your feel, learned
            </h2>
            {/* 画像在左，「sounds like you」专属卡片贴在右侧（窄屏堆叠）。 */}
            <div className="mt-4 flex flex-col gap-6 lg:flex-row lg:items-start">
              <div className="min-w-0 lg:flex-1">
                <MemoryProfile md={memoryMd} />
              </div>
              {soundsLikeYouCard && slyTrack && (
                <div className="w-full shrink-0 lg:w-60">
                  <p className="font-display mb-2 text-[12px] font-bold uppercase tracking-[0.06em] text-[var(--yellow)]">
                    sounds like you
                  </p>
                  {/* 专属卡片：点开 → 基于画像解释「为什么这听起来像你本人」。 */}
                  <button
                    type="button"
                    onClick={() => void openSlyModal()}
                    aria-label={`Why ${slyTrack.title} sounds like you`}
                    className="group flex w-full flex-col overflow-hidden rounded-[6px] border-[2.5px] border-solid border-[var(--yellow)] bg-[var(--paper)] text-left text-[var(--ink)] shadow-[var(--shadow-block)] outline-none transition-transform hover:-translate-y-1"
                  >
                    <div className="relative aspect-square bg-[var(--color-border)]">
                      <img
                        src={slyTrack.cover}
                        alt={`${slyTrack.title} cover art`}
                        className="absolute inset-0 h-full w-full object-cover"
                      />
                      <span className="font-display absolute bottom-2 left-2 rounded-full border border-[var(--ink)] bg-[var(--yellow)] px-2 py-1 text-[10px] font-bold uppercase tracking-[0.06em] text-[var(--ink)]">
                        ✦ this is you
                      </span>
                    </div>
                    <div className="flex flex-1 flex-col px-3 pb-3 pt-3">
                      <div className="font-display line-clamp-2 text-[16px] font-bold leading-tight">
                        {slyTrack.title}
                      </div>
                      <div className="font-serif mt-0.5 truncate text-[12px] italic opacity-60">
                        by {slyTrack.artist}
                      </div>
                      <span className="font-display mt-3 text-[11px] font-bold uppercase tracking-[0.06em] text-[var(--ink)] opacity-50 transition-opacity group-hover:opacity-90">
                        tap for why →
                      </span>
                    </div>
                  </button>
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
