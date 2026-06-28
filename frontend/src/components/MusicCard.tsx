import { useState, type KeyboardEvent, type MouseEvent } from "react";
import { createPortal } from "react-dom";
import { particleBurst, celebrationBurst } from "../particleBurst";

interface MusicCardProps {
  title: string;
  artist: string;
  cover?: string;
  isPlaying?: boolean;
  liked?: boolean;
  surprise?: boolean;
  // Custom corner badge text (e.g. the "sounds like you" card). Overrides the
  // surprise badge when set.
  badge?: string;
  downloadUrl?: string;
  onOpen?: () => void;
  onLike?: (liked: boolean) => void;
  onDismiss?: () => void;
}

const HeartIcon = ({ filled }: { filled: boolean }) => (
  <svg
    viewBox="0 0 24 24"
    width="20"
    height="20"
    fill={filled ? "var(--red)" : "none"}
    stroke={filled ? "var(--red)" : "currentColor"}
    strokeWidth="1.8"
    strokeLinecap="round"
    strokeLinejoin="round"
    aria-hidden="true"
  >
    <path d="M12 21.35l-1.45-1.32C5.4 15.36 2 12.28 2 8.5 2 5.42 4.42 3 7.5 3c1.74 0 3.41.81 4.5 2.09C13.09 3.81 14.76 3 16.5 3 19.58 3 22 5.42 22 8.5c0 3.78-3.4 6.86-8.55 11.54L12 21.35z" />
  </svg>
);

const DownloadIcon = () => (
  <svg
    viewBox="0 0 24 24"
    width="20"
    height="20"
    fill="none"
    stroke="currentColor"
    strokeWidth="1.8"
    strokeLinecap="round"
    strokeLinejoin="round"
    aria-hidden="true"
  >
    <path d="M12 3v12m0 0 4-4m-4 4-4-4M5 21h14" />
  </svg>
);

const CloseIcon = () => (
  <svg
    viewBox="0 0 24 24"
    width="20"
    height="20"
    fill="none"
    stroke="currentColor"
    strokeWidth="1.8"
    strokeLinecap="round"
    strokeLinejoin="round"
    aria-hidden="true"
  >
    <path d="M18 6 6 18M6 6l12 12" />
  </svg>
);

const MusicCard = ({
  title,
  artist,
  cover,
  isPlaying = false,
  liked: likedProp,
  surprise = false,
  badge,
  downloadUrl,
  onOpen,
  onLike,
  onDismiss,
}: MusicCardProps) => {
  const [localLiked, setLocalLiked] = useState(false);
  const [showLicense, setShowLicense] = useState(false);
  const liked = likedProp ?? localLiked;

  const handleKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    if (event.key !== "Enter" && event.key !== " ") return;
    event.preventDefault();
    onOpen?.();
  };

  // Celebrate the surprise card with confetti each time it's hovered.
  const handleMouseEnter = (event: MouseEvent<HTMLDivElement>) => {
    if (!surprise) return;
    const rect = event.currentTarget.getBoundingClientRect();
    celebrationBurst(rect.left + rect.width / 2, rect.top + rect.height / 2);
  };

  const handleLike = (event: MouseEvent<HTMLButtonElement>) => {
    event.stopPropagation();
    const next = !liked;
    setLocalLiked(next);
    if (next) {
      const rect = event.currentTarget.getBoundingClientRect();
      particleBurst(rect.left + rect.width / 2, rect.top + rect.height / 2);
    }
    onLike?.(next);
  };

  const handleDismiss = (event: MouseEvent<HTMLButtonElement>) => {
    event.stopPropagation();
    onDismiss?.();
  };

  return (
    <div
      role="button"
      tabIndex={0}
      onClick={onOpen}
      onKeyDown={handleKeyDown}
      onMouseEnter={handleMouseEnter}
      aria-label={`${title} by ${artist}${surprise ? " — special treat" : ""}`}
      className="flex w-52 flex-col overflow-hidden rounded-[6px] bg-[var(--paper)] text-[var(--ink)] shadow-[var(--shadow-block)] outline-none"
    >
      <div className="relative aspect-square bg-[var(--color-border)]">
        {cover && (
          <img
            src={cover}
            alt={`${title} cover art`}
            loading="eager"
            className="absolute inset-0 h-full w-full object-cover"
          />
        )}
        {(badge || surprise) && (
          <span className="font-display absolute bottom-2 left-2 rounded-full border border-[var(--ink)] bg-[var(--yellow)] px-2 py-1 text-[10px] font-bold uppercase tracking-[0.06em] text-[var(--ink)]">
            {badge ?? "✨ Special treat"}
          </span>
        )}
        {isPlaying && (
          <span
            aria-label="Now playing"
            className="absolute left-2 top-2 flex items-end gap-[3px] rounded bg-[rgba(27,27,27,.7)] px-1.5 py-1"
          >
            {[0, 1, 2].map((bar) => (
              <span
                key={bar}
                className="w-[3px] animate-bounce rounded-sm bg-[var(--paper)]"
                style={{ height: 6 + bar * 4, animationDelay: `${bar * 120}ms` }}
              />
            ))}
          </span>
        )}
      </div>

      <div className="flex flex-1 flex-col px-3 pt-3">
        <div className="font-display line-clamp-2 text-[16px] font-bold leading-tight">
          {title}
        </div>
        <div className="font-serif mt-0.5 truncate text-[12px] italic opacity-60">
          by {artist}
        </div>

        <div className="mt-auto flex justify-end gap-1 pb-3 pt-2">
          {downloadUrl && (
            <button
              type="button"
              onClick={(event) => {
                event.stopPropagation();
                setShowLicense(true);
              }}
              aria-label="Download (high quality)"
              className="flex h-9 w-9 items-center justify-center rounded-[6px] opacity-60 transition hover:bg-[rgba(27,27,27,.08)] hover:opacity-100"
            >
              <DownloadIcon />
            </button>
          )}
          <button
            type="button"
            onClick={handleLike}
            aria-label="Like"
            aria-pressed={liked}
            className="flex h-9 w-9 items-center justify-center rounded-[6px] transition hover:bg-[rgba(237,32,36,.08)] hover:text-[var(--red)]"
            style={{ color: liked ? "var(--red)" : undefined, opacity: liked ? 1 : 0.6 }}
          >
            <HeartIcon filled={liked} />
          </button>
          <button
            type="button"
            onClick={handleDismiss}
            aria-label="Not interested"
            className="flex h-9 w-9 items-center justify-center rounded-[6px] opacity-60 transition hover:bg-[rgba(27,27,27,.08)] hover:opacity-100"
          >
            <CloseIcon />
          </button>
        </div>
      </div>

      {showLicense &&
        downloadUrl &&
        createPortal(
          <div
            className="fixed inset-0 z-[20000] flex items-center justify-center bg-[rgba(27,27,27,.88)] p-6 backdrop-blur-sm"
            onClick={() => setShowLicense(false)}
          >
            <section
              role="dialog"
              aria-modal="true"
              aria-labelledby="download-license-title"
              onClick={(event) => event.stopPropagation()}
              className="w-full max-w-md rounded-[10px] bg-[var(--paper)] p-8 text-[var(--ink)] shadow-[var(--shadow-block)]"
            >
              <h2
                id="download-license-title"
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
              <div className="mt-7 flex justify-end gap-3">
                <button
                  type="button"
                  onClick={() => setShowLicense(false)}
                  className="font-display rounded-full px-5 py-2.5 text-[14px] font-bold uppercase opacity-60 transition hover:opacity-100"
                >
                  Cancel
                </button>
                <a
                  href={downloadUrl}
                  download
                  onClick={() => setShowLicense(false)}
                  className="font-display rounded-full border border-[var(--ink)] px-2.5 py-1 text-[11px] font-bold uppercase leading-none text-[var(--ink)] transition-colors hover:border-[var(--yellow)] hover:bg-[var(--yellow)] hover:text-[var(--ink)]"
                >
                  Download
                </a>
              </div>
            </section>
          </div>,
          document.body,
        )}
    </div>
  );
};

export default MusicCard;
