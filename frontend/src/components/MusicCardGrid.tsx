import { useEffect, useRef } from "react";
// Side-effect import: registers window.MusicCards and injects its own CSS/font.
import "../vendor/music-cards.js";

interface MusicCardGridProps {
  tracks: MusicCardsTrack[];
  coverBase?: string;
  onVote?: (track: MusicCardsTrack, value: "like" | null | "dislike") => void;
  onSelect?: (track: MusicCardsTrack) => void;
}

// Thin React wrapper around the vendored vanilla card grid. It owns a plain
// container div and (re)renders the grid into it whenever the inputs change.
const MusicCardGrid = ({
  tracks,
  coverBase = "/pic/",
  onVote,
  onSelect,
}: MusicCardGridProps) => {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;
    window.MusicCards.renderCardGrid(container, tracks, {
      coverBase,
      onVote,
      onSelect,
    });
    return () => container.replaceChildren();
  }, [tracks, coverBase, onVote, onSelect]);

  return <div ref={containerRef} />;
};

export default MusicCardGrid;
