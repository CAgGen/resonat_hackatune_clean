// Temporary sample tracks for testing playback + cover art. Real cards will
// come from the backend's confirm()/feedback() later. Audio URLs use real rows
// from data/tracks.csv; covers are local files from public/pic.

export interface SampleTrack {
  id: string;
  title: string;
  artist: string;
  url: string;
  cover: string;
}

// Mirrors the backend audio_url() / README pattern.
export const trackUrl = (trackId: string | number) =>
  `https://prod-1.storage.jamendo.com/download/track/${trackId}/mp32/`;

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
