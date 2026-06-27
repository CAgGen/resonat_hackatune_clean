import { useState } from "react";
import ThumbsUp from "./icons/ThumbsUp";
import ThumbsDown from "./icons/ThumbsDown";

type Verdict = "like" | "dislike" | null;

interface MusicCardProps {
  // The card is the chosen/front one in the fan — show its feedback controls.
  active?: boolean;
}

// Blank placeholder track card. Will later host a real music widget and map the
// thumbs to feedback(session_id, track_id, "like"|"dislike") from api.ts.
const MusicCard = ({ active = false }: MusicCardProps) => {
  const [verdict, setVerdict] = useState<Verdict>(null);

  // Clicking the active verdict again clears it back to neutral.
  const toggle = (next: Exclude<Verdict, null>) =>
    setVerdict((prev) => (prev === next ? null : next));

  return (
    <div className="flex h-full w-full flex-col rounded-2xl bg-neutral-200 p-4 text-neutral-700 shadow-2xl">
      <div className="flex flex-1 items-center justify-center">
        <span className="text-base text-neutral-500">playing… music widget</span>
      </div>

      {active && (
        <div className="flex items-center justify-end gap-2">
          <button
            type="button"
            onClick={() => toggle("like")}
            aria-label="Thumbs up"
            aria-pressed={verdict === "like"}
            title="I like this"
            className={`flex h-9 w-9 items-center justify-center rounded-full border transition-colors ${
              verdict === "like"
                ? "border-indigo-500 bg-indigo-500 text-white"
                : "border-neutral-400 text-neutral-500 hover:text-neutral-800"
            }`}
          >
            <ThumbsUp size={18} />
          </button>
          <button
            type="button"
            onClick={() => toggle("dislike")}
            aria-label="Thumbs down"
            aria-pressed={verdict === "dislike"}
            title="Not for me"
            className={`flex h-9 w-9 items-center justify-center rounded-full border transition-colors ${
              verdict === "dislike"
                ? "border-neutral-700 bg-neutral-700 text-white"
                : "border-neutral-400 text-neutral-500 hover:text-neutral-800"
            }`}
          >
            <ThumbsDown size={18} />
          </button>
        </div>
      )}
    </div>
  );
};

export default MusicCard;
