// Temporary sample tracks for testing playback + cover art. Real cards will
// come from the backend's confirm()/feedback() later. Audio URLs use real rows
// from data/tracks.csv; covers are local files from public/pic.

export interface SampleTrack {
  id: string;
  // Numeric Jamendo id, used for the download proxy. For real cards this differs
  // from `id` (which is the Cyanite id); for samples below they're the same.
  trackId?: string;
  title: string;
  artist: string;
  url: string;
  cover: string;
  // Backend marks the deliberate "special treat" card (source==="surprise").
  surprise?: boolean;
}

// Mirrors the backend audio_url() / README pattern.
// Preview uses mp31 (96kbps) for fast buffering; download uses mp32 (high quality).
export const trackUrl = (trackId: string | number) =>
  `https://prod-1.storage.jamendo.com/download/track/${trackId}/mp31/`;

// Routes through the backend proxy: Jamendo blocks direct browser downloads
// (anti-hotlink 403 on top-level navigation, no CORS), so the server fetches
// the high-quality mp32 with a Referer header and streams it back.
export const downloadUrl = (trackId: string | number) =>
  `/api/download/${trackId}`;

export const SAMPLE_TRACKS: SampleTrack[] = [
  { id: "161538", title: "Constellation", artist: "Reno Project", url: trackUrl("161538"), cover: "/pic/100539absdl.jpg" },
  { id: "161536", title: "Afterwork", artist: "Reno Project", url: trackUrl("161536"), cover: "/pic/913542absdl.jpg" },
  { id: "161537", title: "Atlanta", artist: "Reno Project", url: trackUrl("161537"), cover: "/pic/255654fgsdl.jpg" },
  { id: "161539", title: "Down", artist: "Reno Project", url: trackUrl("161539"), cover: "/pic/600454slsdl.jpg" },
  { id: "161535", title: "73rd Moon", artist: "Reno Project", url: trackUrl("161535"), cover: "/pic/962887ilsdl.jpg" },
  { id: "161540", title: "Friday", artist: "Reno Project", url: trackUrl("161540"), cover: "/pic/105710absdl.jpg" },
  { id: "161541", title: "Hot Street", artist: "Reno Project", url: trackUrl("161541"), cover: "/pic/913209absdl.jpg" },
  { id: "161542", title: "Loft Side", artist: "Reno Project", url: trackUrl("161542"), cover: "/pic/516645ldsdl.jpg" },
  { id: "161543", title: "Night Spot", artist: "Reno Project", url: trackUrl("161543"), cover: "/pic/255411fgsdl.jpg" },
  { id: "161544", title: "System", artist: "Reno Project", url: trackUrl("161544"), cover: "/pic/604655slsdl.jpg" },
  { id: "161545", title: "The Field", artist: "Reno Project", url: trackUrl("161545"), cover: "/pic/963027ilsdl.jpg" },
];

// Full pool of cover images in public/pic (23). Used to assign pseudo covers
// with enough variety to keep on-screen cards from sharing one.
export const COVER_POOL: string[] = [
  "/pic/100057absdl.jpg",
  "/pic/100539absdl.jpg",
  "/pic/1002710ilsdl.jpg",
  "/pic/101965absdl.jpg",
  "/pic/105470absdl.jpg",
  "/pic/105710absdl.jpg",
  "/pic/106042absdl.jpg",
  "/pic/255411fgsdl.jpg",
  "/pic/255654fgsdl.jpg",
  "/pic/501995ldsdl.jpg",
  "/pic/516645ldsdl.jpg",
  "/pic/600451slsdl.jpg",
  "/pic/600454slsdl.jpg",
  "/pic/604655slsdl.jpg",
  "/pic/62427drsdl.jpg",
  "/pic/912468absdl.jpg",
  "/pic/913209absdl.jpg",
  "/pic/913281absdl.jpg",
  "/pic/913542absdl.jpg",
  "/pic/962703ilsdl.jpg",
  "/pic/962887ilsdl.jpg",
  "/pic/963027ilsdl.jpg",
  "/pic/963042ilsdl.jpg",
];
