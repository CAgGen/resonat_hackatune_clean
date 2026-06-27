// Types for the vendored, dependency-free music-cards.js (UMD: registers
// window.MusicCards and runs its IIFE on import). The module itself is plain
// JS and isn't type-checked; this just describes its public surface.

interface MusicCardsTrack {
  track: string;
  artist: string;
  cover?: string;
  onSelect?: (track: MusicCardsTrack) => void;
  onVote?: (track: MusicCardsTrack, value: "like" | null | "dislike") => void;
}

interface MusicCardsOptions {
  coverBase?: string;
  covers?: string[];
  randomCovers?: boolean;
  onSelect?: (track: MusicCardsTrack) => void;
  onVote?: (track: MusicCardsTrack, value: "like" | null | "dislike") => void;
}

interface MusicCardsApi {
  renderCardGrid: (
    container: HTMLElement,
    tracks: MusicCardsTrack[],
    opts?: MusicCardsOptions,
  ) => HTMLElement;
  createCard: (track: MusicCardsTrack) => HTMLElement;
  COVER_POOL: string[];
}

interface Window {
  MusicCards: MusicCardsApi;
}

// Side-effect import of the vendored file (it has no ESM exports).
declare module "*/music-cards.js";
