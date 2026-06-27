import { useEffect, useRef, type CSSProperties } from "react";
import type { Note } from "../types";
import { colorForIndex } from "../noteColors";

interface NoteCardProps {
  note: Note;
  index: number;
  onChange?: (id: string, body: string) => void;
  onFinishEdit?: () => void;
  widthClass?: string;
  readOnly?: boolean;
  viewTransitionName?: string;
  // Fill the parent's height (used inside the fixed-size stack slot).
  fill?: boolean;
}

const NoteCard = ({
  note,
  index,
  onChange,
  onFinishEdit,
  widthClass = "w-80",
  readOnly = false,
  viewTransitionName,
  fill = false,
}: NoteCardProps) => {
  const textAreaRef = useRef<HTMLTextAreaElement>(null);
  const color = colorForIndex(index);
  const cardStyle: CSSProperties = {
    backgroundColor: color.body,
    viewTransitionName,
  };

  // Grow the textarea to fit its content (on mount and whenever the body changes).
  const autoGrow = () => {
    const el = textAreaRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${el.scrollHeight}px`;
  };

  useEffect(() => {
    autoGrow();
  }, [note.body]);

  return (
    <div
      className={`${widthClass} ${fill ? "flex h-full flex-col" : ""} overflow-hidden rounded-[10px] border border-[rgba(27,27,27,.16)] shadow-[var(--shadow-block)]`}
      style={cardStyle}
    >
      <div className="h-7" style={{ backgroundColor: color.header }} />
      <div className={`p-4 ${fill ? "min-h-0 flex-1 overflow-hidden" : ""}`}>
        <textarea
          ref={textAreaRef}
          value={note.body}
          onChange={(e) => onChange?.(note.id, e.target.value)}
          onBlur={onFinishEdit}
          readOnly={readOnly}
          placeholder="Describe the music you want…"
          rows={3}
          className="font-hand w-full resize-none overflow-hidden bg-transparent text-[26px] font-semibold leading-[1.1] outline-none placeholder:opacity-50"
          style={{ color: color.text }}
        />
      </div>
    </div>
  );
};

export default NoteCard;
