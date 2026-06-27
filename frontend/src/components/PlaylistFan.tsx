import { useCallback, useEffect, useRef, useState } from "react";
import { AnimatePresence, motion } from "motion/react";
import MusicCard from "./MusicCard";
import TrackReasonModal from "./TrackReasonModal";
import { useAudioPlayer } from "../hooks/useAudioPlayer";
import { SAMPLE_TRACKS, type SampleTrack } from "../sampleTracks";

// Fan geometry per slot: horizontal offset, vertical drop, rotation, resting
// scale and z-index. The middle slot is the default "chosen" card.
const SLOTS = [
  { x: -312, y: 58, rot: -16, z: 8 },
  { x: -156, y: 26, rot: -8, z: 14 },
  { x: 0, y: 0, rot: 0, z: 20 },
  { x: 156, y: 26, rot: 8, z: 14 },
  { x: 312, y: 58, rot: 16, z: 8 },
];
const CENTER_SLOT = Math.floor(SLOTS.length / 2);
const PRELOAD_ORDER = [CENTER_SLOT, 1, 3, 0, 4];
const HOVER_PLAY_DELAY_MS = 180;
const REPLACE_CARD_DELAY_MS = 240;
const CHOSEN_CARD_SCALE = 1.1;
const UNCHOSEN_CARD_SCALE = 0.82;
const FAN_WIDTH = 860;
const FAN_HEIGHT = 440;
const MIN_FAN_SCALE = 0.38;

interface FanCard {
  instanceId: number;
  track: SampleTrack;
}

const PlaylistFan = () => {
  const [cards, setCards] = useState<(FanCard | null)[]>(() =>
    SLOTS.map((_, i) => ({ instanceId: i, track: SAMPLE_TRACKS[i] })),
  );
  const [hovered, setHovered] = useState<number | null>(null);
  const [selected, setSelected] = useState<SampleTrack | null>(null);
  const [fanScale, setFanScale] = useState(1);

  // Rotating pointer into the track pool + a monotonic key for AnimatePresence.
  const next = useRef({ trackIdx: SLOTS.length, instanceId: SLOTS.length });
  const fanRef = useRef<HTMLDivElement>(null);
  const hoverTimer = useRef<number | null>(null);
  const replaceTimers = useRef<number[]>([]);

  const { playingId, play, stop } = useAudioPlayer(SAMPLE_TRACKS, PRELOAD_ORDER);

  const activeIndex = hovered ?? CENTER_SLOT;

  const clearHoverTimer = () => {
    if (hoverTimer.current !== null) {
      window.clearTimeout(hoverTimer.current);
      hoverTimer.current = null;
    }
  };
  useEffect(() => clearHoverTimer, []);

  useEffect(
    () => () => {
      for (const timer of replaceTimers.current) {
        window.clearTimeout(timer);
      }
    },
    [],
  );

  useEffect(() => {
    const element = fanRef.current;
    if (!element) return;

    const updateScale = () => {
      const nextScale = Math.min(
        1,
        Math.max(MIN_FAN_SCALE, element.clientWidth / FAN_WIDTH),
      );
      setFanScale((current) =>
        Math.abs(current - nextScale) < 0.01 ? current : nextScale,
      );
    };

    updateScale();
    const observer = new ResizeObserver(updateScale);
    observer.observe(element);
    window.addEventListener("resize", updateScale);

    return () => {
      observer.disconnect();
      window.removeEventListener("resize", updateScale);
    };
  }, []);

  const handleVote = useCallback(
    (track: SampleTrack, value: "like" | null | "dislike") =>
      console.log("vote:", track.title, value),
    [],
  );

  // Hover-to-play, debounced so a quick pass-over doesn't fire a request.
  const handleEnter = (slot: number, track: SampleTrack) => {
    setHovered(slot);
    clearHoverTimer();
    hoverTimer.current = window.setTimeout(
      () => play(track.id),
      HOVER_PLAY_DELAY_MS,
    );
  };

  const handleLeave = () => {
    setHovered(null);
    clearHoverTimer();
    stop();
  };

  const chooseNextTrack = (visible: string[]) => {
    let chosen = SAMPLE_TRACKS[next.current.trackIdx % SAMPLE_TRACKS.length];
    for (let step = 0; step < SAMPLE_TRACKS.length; step++) {
      const candidate =
        SAMPLE_TRACKS[next.current.trackIdx % SAMPLE_TRACKS.length];
      next.current.trackIdx += 1;
      if (!visible.includes(candidate.id)) {
        chosen = candidate;
        break;
      }
    }
    return chosen;
  };

  // Dismiss first, then slot in a fresh track after the exit motion has room.
  const dismiss = (slotIndex: number, track: SampleTrack) => {
    handleVote(track, "dislike");
    setHovered(null);
    clearHoverTimer();
    stop();
    setCards((prev) => {
      const copy = prev.slice();
      copy[slotIndex] = null;
      return copy;
    });

    const timer = window.setTimeout(() => {
      replaceTimers.current = replaceTimers.current.filter((id) => id !== timer);
      setCards((prev) => {
        const visible = prev
          .map((c) => c?.track.id)
          .filter((id): id is string => Boolean(id));
        const chosen = chooseNextTrack(visible);
        const copy = prev.slice();
        copy[slotIndex] = {
          instanceId: next.current.instanceId++,
          track: chosen,
        };
        return copy;
      });
    }, REPLACE_CARD_DELAY_MS);
    replaceTimers.current.push(timer);
  };

  return (
    <div
      ref={fanRef}
      className="relative w-full"
      style={{ height: Math.max(220, FAN_HEIGHT * fanScale) }}
    >
      <div
        className="absolute left-1/2 top-1/2 h-[440px] w-[860px] origin-center"
        style={{ transform: `translate(-50%, -50%) scale(${fanScale})` }}
      >
        {SLOTS.map((slot, i) => {
          const card = cards[i];
          const isActive = i === activeIndex;
          return (
            <div
              key={i}
              className="absolute left-1/2 top-1/2"
              style={{
                transform: `translate(-50%, -50%) translateX(${slot.x}px)`,
                zIndex: hovered === i ? 30 : slot.z,
              }}
              onMouseEnter={() => card && handleEnter(i, card.track)}
              onMouseLeave={handleLeave}
            >
              <AnimatePresence mode="wait">
                {card && (
                  <motion.div
                    key={card.instanceId}
                    className="cursor-pointer"
                    initial={{
                      opacity: 1,
                      scale: UNCHOSEN_CARD_SCALE,
                      x: 42,
                      y: slot.y + 42,
                      rotate: slot.rot + 8,
                    }}
                    animate={{
                      opacity: 1,
                      scale: isActive ? CHOSEN_CARD_SCALE : UNCHOSEN_CARD_SCALE,
                      x: 0,
                      y: isActive ? slot.y - 14 : slot.y,
                      rotate: slot.rot,
                    }}
                    exit={{
                      opacity: 0,
                      scale: 0.6,
                      x: 40,
                      y: slot.y - 64,
                      rotate: slot.rot + 16,
                    }}
                    transition={{ type: "spring", stiffness: 260, damping: 24 }}
                  >
                    <MusicCard
                      title={card.track.title}
                      artist={card.track.artist}
                      cover={card.track.cover}
                      isPlaying={playingId === card.track.id}
                      onOpen={() => setSelected(card.track)}
                      onLike={(liked) =>
                        handleVote(card.track, liked ? "like" : null)
                      }
                      onDismiss={() => dismiss(i, card.track)}
                    />
                  </motion.div>
                )}
              </AnimatePresence>
            </div>
          );
        })}
      </div>

      {selected && (
        <TrackReasonModal
          track={{
            track: selected.title,
            artist: selected.artist,
            cover: selected.cover,
          }}
          onClose={() => setSelected(null)}
        />
      )}
    </div>
  );
};

export default PlaylistFan;
