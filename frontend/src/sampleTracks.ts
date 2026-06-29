// Card type + URL helpers + cover-art pool for the results UI. Cards themselves
// come from the backend (confirm/feedback); covers are local files from public/pic.

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
