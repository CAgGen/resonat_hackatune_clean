import Plus from "./icons/Plus";

interface ControlsProps {
  onAdd: () => void;
}

const Controls = ({ onAdd }: ControlsProps) => {
  return (
    <div className="fixed left-4 top-1/2 z-[10000] -translate-y-1/2 rounded-full bg-[var(--paper)] p-2 shadow-[var(--shadow-block)]">
      <button
        type="button"
        onClick={onAdd}
        aria-label="Add a note"
        title="Add a note"
        className="flex h-11 w-11 items-center justify-center rounded-full bg-[var(--red)] text-[var(--paper)] transition-transform duration-150 hover:-rotate-2 hover:scale-105"
      >
        <Plus size={22} />
      </button>
    </div>
  );
};

export default Controls;
