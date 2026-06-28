import { useEffect, useRef, type CSSProperties } from "react";
import type { Note } from "../types";
import { colorForIndex } from "../noteColors";

type MemoState = "empty" | "typing" | "complete";
type MemoVariantName = "paper" | "pink" | "yellow" | "blue" | "red" | "green";

interface NoteCardProps {
  note: Note;
  index: number;
  onChange?: (id: string, body: string) => void;
  onFinishEdit?: () => void;
  onCommit?: (id: string) => void;
  widthClass?: string;
  readOnly?: boolean;
  viewTransitionName?: string;
  variant?: MemoVariantName;
  // Fill the parent's height (used inside the fixed-size stack slot).
  fill?: boolean;
}

const MEMO_VARIANT_ORDER: MemoVariantName[] = [
  "paper",
  "pink",
  "yellow",
  "blue",
  "red",
  "green",
];

const MEMO_VARIANTS = {
  paper: {
    surface: "#E5E1D6",
    text: "#1B1B1B",
    caret: "#ED2024",
    shadow: "6px 6px 0 0 rgba(229,225,214,.16)",
    border: "1px solid rgba(27,27,27,.14)",
  },
  pink: {
    surface: "#F45CA0",
    text: "#1B1B1B",
    caret: "#1B1B1B",
    shadow: "6px 6px 0 0 #E5E1D6",
    border: "none",
  },
  yellow: {
    surface: "#F6B400",
    text: "#1B1B1B",
    caret: "#ED2024",
    shadow: "6px 6px 0 0 #E5E1D6",
    border: "none",
  },
  blue: {
    surface: "#2C5BC7",
    text: "#E5E1D6",
    caret: "#E5E1D6",
    shadow: "6px 6px 0 0 #E5E1D6",
    border: "none",
  },
  red: {
    surface: "#ED2024",
    text: "#E5E1D6",
    caret: "#E5E1D6",
    shadow: "6px 6px 0 0 #E5E1D6",
    border: "none",
  },
  green: {
    surface: "#189A4C",
    text: "#E5E1D6",
    caret: "#E5E1D6",
    shadow: "6px 6px 0 0 #E5E1D6",
    border: "none",
  },
};

const MEMO_SCALE = [
  { max: 16, size: 30, line: 1.2 },
  { max: 42, size: 24, line: 1.25 },
  { max: 84, size: 20, line: 1.35 },
  { max: 150, size: 17, line: 1.45 },
  { max: 280, size: 15, line: 1.5 },
  { max: Infinity, size: 13, line: 1.55 },
];

const rgba = (hex: string, alpha: number) => {
  const n = Number.parseInt(hex.slice(1), 16);
  return `rgba(${(n >> 16) & 255},${(n >> 8) & 255},${n & 255},${alpha})`;
};

const fitFont = (text = "") => {
  const weight =
    text.replace(/\n/g, "").length + (text.match(/\n/g)?.length ?? 0) * 14;
  return MEMO_SCALE.find((step) => weight <= step.max) ?? MEMO_SCALE.at(-1)!;
};

const parseNoteDate = (value: string) => {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? new Date() : date;
};

const metaText = (date: Date | null) => {
  if (!date) return "date:  /  / __:__";
  const pad = (value: number) => String(value).padStart(2, "0");
  return `date: ${pad(date.getMonth() + 1)} / ${pad(date.getDate())} / ${pad(
    date.getHours(),
  )}:${pad(date.getMinutes())}`;
};

const NoteCard = ({
  note,
  index,
  onChange,
  onFinishEdit,
  onCommit,
  widthClass = "w-80",
  readOnly = false,
  viewTransitionName,
  variant,
  fill = false,
}: NoteCardProps) => {
  const textAreaRef = useRef<HTMLTextAreaElement>(null);
  const cardRef = useRef<HTMLDivElement>(null);
  const footerRef = useRef<HTMLDivElement>(null);
  const hintRef = useRef<HTMLDivElement>(null);
  const settledDateRef = useRef<Date | null>(parseNoteDate(note.createdAt));
  const stateRef = useRef<MemoState>(
    note.body.trim() ? "complete" : "empty",
  );
  const setMemoStateRef = useRef<(next: MemoState) => void>(() => undefined);
  const legacyColor = colorForIndex(index);
  const variantName =
    variant ?? MEMO_VARIANT_ORDER[index % MEMO_VARIANT_ORDER.length];
  const memoVariant = MEMO_VARIANTS[variantName] ?? {
    surface: legacyColor.body,
    text: legacyColor.text,
    caret: legacyColor.header,
    shadow: "6px 6px 0 0 #E5E1D6",
    border: "none",
  };
  const softText = rgba(memoVariant.text, 0.55);
  const faintText = rgba(memoVariant.text, 0.3);
  const initialState = stateRef.current;
  const initialFit = fitFont(note.body || "Describe the music you want...");
  const cardStyle: CSSProperties = {
    "--memo-text": memoVariant.text,
    "--memo-caret": memoVariant.caret,
    "--memo-faint": faintText,
    "--memo-shadow": memoVariant.shadow,
    backgroundColor: memoVariant.surface,
    border: memoVariant.border,
    boxShadow: memoVariant.shadow,
    color: memoVariant.text,
    width: "260px",
    height: "260px",
    padding: "22px",
    viewTransitionName,
  } as CSSProperties;

  const applyFit = (text = note.body) => {
    const el = textAreaRef.current;
    if (!el) return;
    const fit = fitFont(text || "Describe the music you want...");
    el.style.fontSize = `${fit.size}px`;
    el.style.lineHeight = String(fit.line);
    el.style.height = "auto";
    el.style.height = `${el.scrollHeight}px`;
  };

  const setMemoState = (next: MemoState) => {
    const card = cardRef.current;
    const footer = footerRef.current;
    const hint = hintRef.current;
    const input = textAreaRef.current;
    stateRef.current = next;
    if (next === "complete" && !settledDateRef.current) {
      settledDateRef.current = new Date();
    }
    card?.setAttribute("data-memo-state", next);
    if (card) {
      card.style.cursor = next === "complete" && !readOnly ? "pointer" : "text";
    }
    if (footer) {
      footer.textContent = metaText(settledDateRef.current);
      footer.style.opacity = next === "complete" ? "1" : "0.6";
    }
    if (hint) {
      hint.style.display = next === "empty" ? "flex" : "none";
    }
    if (input) {
      input.style.caretColor =
        next === "complete" ? "transparent" : memoVariant.caret;
    }
  };
  setMemoStateRef.current = setMemoState;

  useEffect(() => {
    applyFit();
    if (readOnly) {
      setMemoStateRef.current(note.body.trim() ? "complete" : "empty");
    } else if (!note.body.trim() && stateRef.current === "complete") {
      setMemoStateRef.current("empty");
    } else if (
      note.body.trim() &&
      stateRef.current === "typing" &&
      document.activeElement !== textAreaRef.current
    ) {
      if (!settledDateRef.current) {
        settledDateRef.current = new Date();
      }
      setMemoStateRef.current("complete");
    }
  });

  return (
    <div
      ref={cardRef}
      data-memo-state={initialState}
      onMouseDown={(event) => {
        if (readOnly) return;
        const input = textAreaRef.current;
        // Clicking the textarea itself: let the browser place the caret.
        // Clicking anywhere else in the card: focus it and edit.
        if (!input || event.target === input) return;
        event.preventDefault();
        input.focus();
        input.setSelectionRange(input.value.length, input.value.length);
        setMemoState("typing");
      }}
      className={`${widthClass} ${fill ? "flex" : ""} relative box-border grid grid-rows-[1fr_auto] gap-[18px] overflow-hidden rounded-[10px] transition-[box-shadow,transform] duration-150 ease-out focus-within:shadow-[var(--memo-shadow),0_0_0_2px_var(--memo-caret)]`}
      style={cardStyle}
    >
      <div className="relative flex min-h-0 items-center justify-center overflow-hidden">
        <div
          ref={hintRef}
          aria-hidden="true"
          className="pointer-events-none absolute inset-0 items-center justify-center text-center font-sans"
          style={{
            color: faintText,
            display: initialState === "empty" ? "flex" : "none",
            fontSize: `${initialFit.size}px`,
            lineHeight: initialFit.line,
          }}
        >
          <span>
            Describe the music you want...
            <span
              className="ml-1 inline-block h-[1.02em] w-0 animate-pulse border-l-[2px] border-solid align-[-0.16em]"
              style={{ borderColor: memoVariant.caret }}
            />
          </span>
        </div>
        <textarea
          ref={textAreaRef}
          value={note.body}
          onFocus={() => {
            if (!readOnly) setMemoState("typing");
          }}
          onChange={(event) => {
            const next = event.target.value;
            onChange?.(note.id, next);
            applyFit(next);
            setMemoState(next ? "typing" : "empty");
          }}
          onKeyDown={(event) => {
            // Enter builds the prompt straight away (Shift+Enter still wraps).
            if (event.key === "Enter" && !event.shiftKey) {
              event.preventDefault();
              if (textAreaRef.current?.value.trim()) {
                textAreaRef.current.blur();
                onCommit?.(note.id);
                onFinishEdit?.();
              }
            }
          }}
          onBlur={() => {
            const next = textAreaRef.current?.value.trim()
              ? "complete"
              : "empty";
            if (next === "complete" && !settledDateRef.current) {
              settledDateRef.current = new Date();
            }
            setMemoState(next);
          }}
          readOnly={readOnly}
          rows={1}
          aria-label="Memo text"
          className="relative z-10 w-full resize-none overflow-hidden border-0 bg-transparent text-center font-sans outline-none placeholder:text-transparent"
          style={{
            color: memoVariant.text,
            caretColor:
              initialState === "complete" ? "transparent" : memoVariant.caret,
            fontSize: `${initialFit.size}px`,
            lineHeight: initialFit.line,
          }}
        />
      </div>
      <div
        ref={footerRef}
        className="text-center font-sans text-[13px] tracking-[0.02em]"
        style={{
          color: softText,
          opacity: initialState === "complete" ? 1 : 0.6,
        }}
      >
        {metaText(settledDateRef.current)}
      </div>
    </div>
  );
};

export default NoteCard;
