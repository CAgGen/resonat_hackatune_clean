import { useEffect, useRef } from "react";
import type { Note } from "../types";
import { colorForIndex } from "../noteColors";

interface NoteCardProps {
  note: Note;
  index: number;
  onChange?: (id: string, body: string) => void;
  onFinishEdit?: () => void;
  widthClass?: string;
  readOnly?: boolean;
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
  fill = false,
}: NoteCardProps) => {
  const textAreaRef = useRef<HTMLTextAreaElement>(null);
  const color = colorForIndex(index);

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
      className={`${widthClass} ${fill ? "flex h-full flex-col" : ""} overflow-hidden rounded-md shadow-[0_1px_1px_rgba(0,0,0,0.15),0_10px_20px_rgba(0,0,0,0.35)]`}
      style={{ backgroundColor: color.body }}
    >
      <div className="h-6" style={{ backgroundColor: color.header }} />
      <div className={`p-4 ${fill ? "min-h-0 flex-1 overflow-hidden" : ""}`}>
        <textarea
          ref={textAreaRef}
          value={note.body}
          onChange={(e) => onChange?.(note.id, e.target.value)}
          onBlur={onFinishEdit}
          readOnly={readOnly}
          placeholder="Describe the music you want…"
          rows={3}
          className="w-full resize-none overflow-hidden bg-transparent text-base leading-relaxed outline-none placeholder:opacity-50"
          style={{ color: color.text }}
        />
      </div>
    </div>
  );
};

export default NoteCard;
