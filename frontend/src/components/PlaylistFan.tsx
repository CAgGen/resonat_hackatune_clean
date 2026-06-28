import { useEffect, useMemo, useRef, useState } from "react";
import { AnimatePresence, motion } from "motion/react";
import MusicCard from "./MusicCard";
import TrackReasonModal from "./TrackReasonModal";
import { useAudioPlayer } from "../hooks/useAudioPlayer";
import { SAMPLE_TRACKS, downloadUrl, type SampleTrack } from "../sampleTracks";

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

interface PlaylistFanProps {
  tracks?: SampleTrack[];
  antiAddiction?: boolean;
  likedIds?: Set<string>;
  onLike?: (track: SampleTrack) => Promise<void> | void;
  onUnlike?: (track: SampleTrack) => void;
  onDismiss?: (track: SampleTrack) => Promise<void> | void;
  onExplain?: (track: SampleTrack) => Promise<string>;
}

const PlaylistFan = ({
  tracks = SAMPLE_TRACKS.slice(0, SLOTS.length),
  antiAddiction = false,
  likedIds,
  onLike,
  onUnlike,
  onDismiss,
  onExplain,
}: PlaylistFanProps) => {
  const [cards, setCards] = useState<(FanCard | null)[]>([]);
  const [hovered, setHovered] = useState<number | null>(null);
  const [selected, setSelected] = useState<SampleTrack | null>(null);
  const [selectedReason, setSelectedReason] = useState("");
  const [isReasonLoading, setIsReasonLoading] = useState(false);
  const [fanScale, setFanScale] = useState(1);

  const nextInstanceId = useRef(0);
  const fanRef = useRef<HTMLDivElement>(null);
  const hoverTimer = useRef<number | null>(null);
  const replaceTimers = useRef<number[]>([]);
  // Keeps the hovered track playing while its explanation modal is open.
  const modalOpenRef = useRef(false);

  const visibleTracks = useMemo(
    () =>
      cards
        .map((card) => card?.track)
        .filter((track): track is SampleTrack => Boolean(track)),
    [cards],
  );
  const { playingId, play, stop } = useAudioPlayer(visibleTracks, PRELOAD_ORDER);

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
    setCards((prev) =>
      SLOTS.map((_, i) => {
        const track = tracks[i];
        if (!track) return null;
        const current = prev[i];
        if (current?.track.id === track.id) {
          return { ...current, track };
        }
        return {
          instanceId: nextInstanceId.current++,
          track,
        };
      }),
    );
  }, [tracks]);

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
    // Opening the explanation modal triggers a mouseleave on the card — keep
    // the track playing in that case; only stop when the modal isn't open.
    if (!modalOpenRef.current) stop();
  };

  const removeCard = (
    slotIndex: number,
    track: SampleTrack,
    afterRemove?: (track: SampleTrack) => Promise<void> | void,
  ) => {
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
      void afterRemove?.(track);
    }, REPLACE_CARD_DELAY_MS);
    replaceTimers.current.push(timer);
  };

  const dismiss = (slotIndex: number, track: SampleTrack) => {
    removeCard(slotIndex, track, onDismiss);
  };

  const like = (slotIndex: number, track: SampleTrack, liked: boolean) => {
    if (!liked) {
      onUnlike?.(track);
      return;
    }
    if (antiAddiction) {
      void onLike?.(track);
      return;
    }
    removeCard(slotIndex, track, onLike);
  };

  // 打开卡片即取解释——「why this song」按钮已删，改为自动加载。
  const openTrack = (track: SampleTrack) => {
    modalOpenRef.current = true;
    play(track.id);
    setSelected(track);
    setSelectedReason("");
    setIsReasonLoading(true);
    void onExplain?.(track)
      .then((reason) => setSelectedReason(reason))
      .catch(() =>
        setSelectedReason(
          "The detailed explanation is still loading. This track came from your confirmed sound brief and Cyanite audio matching.",
        ),
      )
      .finally(() => setIsReasonLoading(false));
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
                      liked={likedIds?.has(card.track.id) ?? false}
                      surprise={card.track.surprise ?? false}
                      downloadUrl={
                        (card.track.trackId ?? card.track.id).match(/^\d+$/)
                          ? downloadUrl(card.track.trackId ?? card.track.id)
                          : undefined
                      }
                      onOpen={() => openTrack(card.track)}
                      onLike={(liked) => {
                        like(i, card.track, liked);
                      }}
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
          reasonText={selectedReason}
          isLoading={isReasonLoading}
          onClose={() => {
            modalOpenRef.current = false;
            setSelected(null);
          }}
        />
      )}
    </div>
  );
};

export default PlaylistFan;
