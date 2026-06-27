export interface NoteColor {
  header: string;
  body: string;
  text: string;
}

export const NOTE_COLORS: NoteColor[] = [
  { header: "#ED2024", body: "#E5E1D6", text: "#1B1B1B" },
  { header: "#189A4C", body: "#E5E1D6", text: "#1B1B1B" },
  { header: "#F45CA0", body: "#E5E1D6", text: "#1B1B1B" },
  { header: "#2C5BC7", body: "#E5E1D6", text: "#1B1B1B" },
  { header: "#F6B400", body: "#E5E1D6", text: "#1B1B1B" },
];

export const colorForIndex = (index: number): NoteColor =>
  NOTE_COLORS[index % NOTE_COLORS.length];
