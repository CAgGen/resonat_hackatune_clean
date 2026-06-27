import Plus from "./icons/Plus";

interface AddNoteButtonProps {
  onClick: () => void;
}

// The single, consistent "add a post-it" button (starting-page style).
const AddNoteButton = ({ onClick }: AddNoteButtonProps) => (
  <button
    type="button"
    onClick={onClick}
    aria-label="Add a note"
    title="Add a note"
    className="flex h-16 w-16 -rotate-3 items-center justify-center rounded-full bg-[var(--yellow)] text-[var(--ink)] shadow-[var(--shadow-block)] transition-transform duration-150 hover:rotate-0 hover:scale-105"
  >
    <Plus size={30} />
  </button>
);

export default AddNoteButton;
