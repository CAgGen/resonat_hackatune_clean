import { useEffect, useState } from "react";
import heroArt from "../assets/hero.png";
import MusicCard from "./MusicCard";

// Fan geometry per slot: horizontal offset, vertical drop, rotation, resting
// scale and z-index. The middle slot is the default "chosen" card.
const FAN = [
  { id: "left", x: -170, y: 28, rot: -10, scale: 0.92, z: 10 },
  { id: "middle", x: 0, y: 0, rot: 0, scale: 1, z: 20 },
  { id: "right", x: 170, y: 28, rot: 10, scale: 0.92, z: 10 },
];

const REASON_TEXT =
  "This track found you because your sound brief points toward something warm, unhurried, and emotionally close. The recommendation balances soft rhythm, late-night texture, and a gentle lift so the song feels personal without pulling you out of the mood you described.";

const REASON_TOKENS = REASON_TEXT.match(/\S+\s*/g) ?? [];

interface TrackReasonModalProps {
  trackIndex: number;
  onClose: () => void;
}

const TrackReasonModal = ({ trackIndex, onClose }: TrackReasonModalProps) => {
  const [visibleTokens, setVisibleTokens] = useState(0);
  const visibleText = REASON_TOKENS.slice(0, visibleTokens).join("");

  useEffect(() => {
    setVisibleTokens(0);
    const timer = window.setInterval(() => {
      setVisibleTokens((count) => {
        if (count >= REASON_TOKENS.length) {
          window.clearInterval(timer);
          return count;
        }
        return count + 1;
      });
    }, 42);

    return () => window.clearInterval(timer);
  }, [trackIndex]);

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
            src={heroArt}
            alt="Recommended track artwork"
            className="h-full w-full object-contain p-10"
          />
        </div>

        <div className="flex min-h-80 flex-col justify-center">
          <h2
            id="track-reason-title"
            className="font-display text-[40px] font-bold uppercase leading-none tracking-[-0.01em]"
          >
            Why this song found you
          </h2>
          <p className="font-serif mt-6 min-h-40 text-[18px] leading-[1.6] text-[var(--ink)]">
            {visibleText}
            {visibleTokens < REASON_TOKENS.length && (
              <span className="ml-1 inline-block h-5 w-2 animate-pulse rounded-sm bg-[var(--blue)] align-middle" />
            )}
          </p>
        </div>
      </section>
    </div>
  );
};

const PlaylistFan = () => {
  const [hovered, setHovered] = useState<number | null>(null);
  const [selectedTrack, setSelectedTrack] = useState<number | null>(null);
  // Default chosen card is the middle one; hovering overrides it.
  const activeIndex = hovered ?? 1;

  return (
    <div className="relative h-80 w-full">
      {FAN.map((slot, i) => {
        const isActive = i === activeIndex;
        const lift = isActive ? 18 : 0;
        const scale = isActive ? slot.scale * 1.12 : slot.scale;
        return (
          <div
            key={slot.id}
            onMouseEnter={() => setHovered(i)}
            onMouseLeave={() => setHovered(null)}
            className="absolute left-1/2 top-1/2 h-56 w-72 cursor-pointer transition-all duration-150 ease-out"
            style={{
              transform: `translate(-50%, -50%) translateX(${slot.x}px) translateY(${slot.y - lift}px) rotate(${slot.rot}deg) scale(${scale})`,
              zIndex: isActive ? 30 : slot.z,
              // Non-chosen cards grey out.
              opacity: isActive ? 1 : 0.5,
            }}
          >
            <MusicCard active={isActive} onOpen={() => setSelectedTrack(i)} />
          </div>
        );
      })}
      {selectedTrack !== null && (
        <TrackReasonModal
          trackIndex={selectedTrack}
          onClose={() => setSelectedTrack(null)}
        />
      )}
    </div>
  );
};

export default PlaylistFan;
