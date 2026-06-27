import { useCallback, useEffect, useRef, useState } from "react";

export interface PlayerTrack {
  id: string;
  url: string;
}

const PRELOAD_TIMEOUT_MS = 20000;

// Manages one-at-a-time audio playback for a small set of tracks, plus a
// SEQUENTIAL preload queue (one request at a time) so we don't trip Jamendo's
// burst rate-limiting.
export function useAudioPlayer(
  tracks: PlayerTrack[],
  // Indices into `tracks` controlling preload order (e.g. middle card first).
  preloadOrder?: number[],
) {
  const [playingId, setPlayingId] = useState<string | null>(null);
  const [unavailable, setUnavailable] = useState<Set<string>>(new Set());
  const audiosRef = useRef<Map<string, HTMLAudioElement>>(new Map());

  const markUnavailable = useCallback((id: string) => {
    setUnavailable((prev) => (prev.has(id) ? prev : new Set(prev).add(id)));
  }, []);

  useEffect(() => {
    const audios = new Map<string, HTMLAudioElement>();
    for (const track of tracks) {
      const audio = new Audio();
      audio.preload = "none";
      audio.src = track.url;
      audios.set(track.id, audio);
    }
    audiosRef.current = audios;

    // Sequential preload: warm one file at a time. Preload is BEST-EFFORT — a
    // transient throttle here must not flag a track (it usually plays fine on
    // hover, and StrictMode teardown also fires spurious errors). Only a real
    // play() failure marks a track unavailable (see `play`).
    const order = preloadOrder ?? tracks.map((_, i) => i);
    let cancelled = false;
    let cursor = 0;

    const preloadNext = () => {
      if (cancelled || cursor >= order.length) return;
      const track = tracks[order[cursor]];
      const audio = track && audios.get(track.id);
      if (!track || !audio) {
        cursor += 1;
        preloadNext();
        return;
      }

      let settled = false;
      const advance = () => {
        if (settled) return;
        settled = true;
        window.clearTimeout(timer);
        audio.removeEventListener("canplaythrough", advance);
        audio.removeEventListener("error", advance);
        cursor += 1;
        preloadNext();
      };

      // Move on whether the file buffered, errored, or timed out.
      audio.addEventListener("canplaythrough", advance, { once: true });
      audio.addEventListener("error", advance, { once: true });
      const timer = window.setTimeout(advance, PRELOAD_TIMEOUT_MS);

      audio.preload = "auto";
      audio.load();
    };

    preloadNext();

    return () => {
      cancelled = true;
      for (const audio of audios.values()) {
        audio.pause();
        audio.removeAttribute("src");
      }
      audiosRef.current = new Map();
    };
  }, [tracks, preloadOrder]);

  const stop = useCallback(() => {
    for (const audio of audiosRef.current.values()) audio.pause();
    setPlayingId(null);
  }, []);

  const play = useCallback(
    (id: string) => {
      const audios = audiosRef.current;
      const target = audios.get(id);
      if (!target) return;
      for (const [key, audio] of audios) {
        if (key !== id) audio.pause();
      }
      target.preload = "auto";
      void target
        .play()
        .then(() => setPlayingId(id))
        .catch(() => {
          setPlayingId((current) => (current === id ? null : current));
          // Only flag genuinely unplayable resources: DECODE (3) or
          // SRC_NOT_SUPPORTED (4). ABORTED (1) and NETWORK (2) are transient
          // (Jamendo throttling / hovering away) and can recover on retry.
          // A blocked-autoplay rejection leaves `target.error` null.
          const code = target.error?.code;
          if (code === 3 || code === 4) markUnavailable(id);
        });
    },
    [markUnavailable],
  );

  return { playingId, unavailable, play, stop };
}
