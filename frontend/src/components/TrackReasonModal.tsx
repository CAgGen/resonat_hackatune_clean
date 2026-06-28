import { useEffect, useState } from "react";
import heroArt from "../assets/hero.png";
import type { MoodSegment } from "../api";

interface TrackReasonModalProps {
  track: MusicCardsTrack;
  reasonText?: string;
  segments?: MoodSegment[];
  onSeek?: (seconds: number) => void;
  isLoading?: boolean;
  title?: string;
  onClose: () => void;
}

const fmtTime = (s: number) =>
  `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, "0")}`;

const TrackReasonModal = ({
  track,
  reasonText = "",
  segments = [],
  onSeek,
  isLoading = false,
  title = "why this song found you",
  onClose,
}: TrackReasonModalProps) => {
  const [visibleTokens, setVisibleTokens] = useState(0);
  const tokens = reasonText.match(/\S+\s*/g) ?? [];
  const visibleText = tokens.slice(0, visibleTokens).join("");

  // Typewriter runs once, keyed on the resolved text — not on token length, so
  // the loading→loaded swap no longer resets it mid-type (the "反悔" flicker).
  // ponytail: single fetch upstream, no streaming to reconcile.
  useEffect(() => {
    if (isLoading || tokens.length === 0) return;
    setVisibleTokens(0);
    const timer = window.setInterval(() => {
      setVisibleTokens((count) => {
        if (count >= tokens.length) {
          window.clearInterval(timer);
          return count;
        }
        return count + 1;
      });
    }, 42);

    return () => window.clearInterval(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [reasonText, isLoading]);

  return (
    <div
      className="fixed inset-0 z-[20000] flex items-center justify-center bg-[rgba(27,27,27,.88)] p-6 backdrop-blur-sm"
      onClick={onClose}
    >
      <section
        role="dialog"
        aria-modal="true"
        aria-labelledby="track-reason-title"
        onClick={(event) => event.stopPropagation()}
        className="grid w-full max-w-5xl grid-cols-1 gap-8 rounded-[10px] bg-[var(--paper)] p-8 text-[var(--ink)] shadow-[var(--shadow-block)] md:grid-cols-[0.9fr_1.1fr]"
      >
        <div className="aspect-square overflow-hidden rounded-[10px] bg-[var(--ink)]">
          <img
            src={track.cover ?? heroArt}
            alt="Recommended track artwork"
            className="h-full w-full object-cover"
          />
        </div>

        <div className="flex min-h-80 flex-col justify-center">
          <p className="font-display text-[13px] font-bold uppercase tracking-[0.08em] text-[var(--ink)] opacity-60">
            {track.track} · {track.artist}
          </p>
          <h2
            id="track-reason-title"
            className="font-display mt-2 whitespace-nowrap text-[30px] font-bold leading-none sm:text-[36px]"
          >
            {title}
          </h2>
          <p className="font-serif mt-6 min-h-40 text-[18px] leading-[1.6] text-[var(--ink)]">
            {isLoading ? "Finding the musical evidence..." : visibleText}
            {!isLoading && visibleTokens < tokens.length && (
              <span className="ml-1 inline-block h-5 w-2 animate-pulse rounded-sm bg-[var(--blue)] align-middle" />
            )}
          </p>

          {/* 角标：情绪随时间的时间轴，点一下跳到那一分钟。时间戳直接来自 Cyanite segments。 */}
          {!isLoading && segments.length > 0 && (
            <div className="mt-5">
              <p className="font-display text-[11px] font-bold uppercase tracking-[0.08em] text-[var(--ink)] opacity-50">
                hear it for yourself
              </p>
              <div className="mt-2 flex flex-wrap gap-2">
                {segments.map((seg, i) => (
                  <button
                    key={`${seg.t}-${i}`}
                    type="button"
                    onClick={() => onSeek?.(seg.t)}
                    className="font-display rounded-full border-[2px] border-solid border-[var(--ink)] px-3 py-1 text-[12px] font-bold lowercase text-[var(--ink)] transition-colors hover:bg-[var(--blue)] hover:text-[var(--paper)]"
                  >
                    {fmtTime(seg.t)} · {seg.label}
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>
      </section>
    </div>
  );
};

export default TrackReasonModal;
