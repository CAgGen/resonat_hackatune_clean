import { useState } from "react";
import MusicCard from "./MusicCard";

// Fan geometry per slot: horizontal offset, vertical drop, rotation, resting
// scale and z-index. The middle slot is the default "chosen" card.
const FAN = [
  { id: "left", x: -170, y: 28, rot: -10, scale: 0.92, z: 10 },
  { id: "middle", x: 0, y: 0, rot: 0, scale: 1, z: 20 },
  { id: "right", x: 170, y: 28, rot: 10, scale: 0.92, z: 10 },
];

const PlaylistFan = () => {
  const [hovered, setHovered] = useState<number | null>(null);
  // Default chosen card is the middle one; hovering overrides it.
  const activeIndex = hovered ?? 1;

  return (
    <div className="relative h-80 w-full">
      {FAN.map((slot, i) => {
        const isActive = i === activeIndex;
        const lift = isActive ? 18 : 0;
        const scale = isActive ? slot.scale * 1.12 : slot.scale;
        return (
          <div
            key={slot.id}
            onMouseEnter={() => setHovered(i)}
            onMouseLeave={() => setHovered(null)}
            className="absolute left-1/2 top-1/2 h-56 w-72 cursor-pointer transition-all duration-300 ease-out"
            style={{
              transform: `translate(-50%, -50%) translateX(${slot.x}px) translateY(${slot.y - lift}px) rotate(${slot.rot}deg) scale(${scale})`,
              zIndex: isActive ? 30 : slot.z,
              // Non-chosen cards grey out.
              opacity: isActive ? 1 : 0.5,
            }}
          >
            <MusicCard active={isActive} />
          </div>
        );
      })}
    </div>
  );
};

export default PlaylistFan;
