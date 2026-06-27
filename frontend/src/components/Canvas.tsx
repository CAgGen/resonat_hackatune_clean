import type { ReactNode } from "react";
import GrainientBackground from "./GrainientBackground";

interface CanvasProps {
  children: ReactNode;
}

// The dark "board" with a subtle grid background.
const Canvas = ({ children }: CanvasProps) => (
  <div className="relative isolate min-h-screen w-full overflow-hidden bg-[var(--ink)]">
    <GrainientBackground />
    <div className="relative z-10">{children}</div>
  </div>
);

export default Canvas;
