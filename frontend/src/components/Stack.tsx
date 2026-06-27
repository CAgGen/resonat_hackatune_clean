import { motion } from "motion/react";
import { useEffect, useRef, useState, type ReactNode } from "react";
import "./Stack.css";

interface AnimationConfig {
  stiffness: number;
  damping: number;
}

interface StackProps {
  /** Applies a small random rotation to each card for a "messy" look. */
  randomRotation?: boolean;
  /** Clicking the top card sends it to the back, cycling through the stack. */
  sendToBackOnClick?: boolean;
  /** The card elements to display in the stack. */
  cards: ReactNode[];
  /** Spring stiffness/damping for the shuffle animation. */
  animationConfig?: AnimationConfig;
  /** Automatically cycle through the cards. */
  autoplay?: boolean;
  /** Delay (ms) between automatic transitions. */
  autoplayDelay?: number;
  /** Pause autoplay while hovering the stack. */
  pauseOnHover?: boolean;
}

interface StackCard {
  id: number;
  content: ReactNode;
}

// Drag-free adaptation of the React Bits <Stack /> component: keeps the messy
// rotation, scale offsets and spring physics, and cycles on click — but drops
// the drag-to-send-to-back interaction.
export default function Stack({
  randomRotation = false,
  sendToBackOnClick = true,
  cards,
  animationConfig = { stiffness: 260, damping: 20 },
  autoplay = false,
  autoplayDelay = 3000,
  pauseOnHover = false,
}: StackProps) {
  const [stack, setStack] = useState<StackCard[]>(() =>
    cards.map((content, index) => ({ id: index + 1, content })),
  );
  const [isPaused, setIsPaused] = useState(false);

  // Stable random rotation per card id so it doesn't jitter on every render.
  const rotations = useRef<Record<number, number>>({});

  useEffect(() => {
    setStack(cards.map((content, index) => ({ id: index + 1, content })));
  }, [cards]);

  const sendToBack = (id: number) => {
    setStack((prev) => {
      const next = [...prev];
      const index = next.findIndex((card) => card.id === id);
      const [card] = next.splice(index, 1);
      next.unshift(card);
      return next;
    });
  };

  useEffect(() => {
    if (!autoplay || stack.length <= 1 || isPaused) return;
    const interval = window.setInterval(() => {
      sendToBack(stack[stack.length - 1].id);
    }, autoplayDelay);
    return () => window.clearInterval(interval);
  }, [autoplay, autoplayDelay, stack, isPaused]);

  return (
    <div
      className="stack-container"
      onMouseEnter={() => pauseOnHover && setIsPaused(true)}
      onMouseLeave={() => pauseOnHover && setIsPaused(false)}
    >
      {stack.map((card, index) => {
        let randomRotate = 0;
        if (randomRotation) {
          if (rotations.current[card.id] === undefined) {
            rotations.current[card.id] = Math.random() * 10 - 5;
          }
          randomRotate = rotations.current[card.id];
        }

        return (
          <motion.div
            key={card.id}
            className="stack-card"
            style={{ cursor: sendToBackOnClick ? "pointer" : "default" }}
            onClick={() => sendToBackOnClick && sendToBack(card.id)}
            animate={{
              rotateZ: (stack.length - index - 1) * 4 + randomRotate,
              scale: 1 + index * 0.06 - stack.length * 0.06,
              transformOrigin: "90% 90%",
            }}
            initial={false}
            transition={{
              type: "spring",
              stiffness: animationConfig.stiffness,
              damping: animationConfig.damping,
            }}
          >
            {card.content}
          </motion.div>
        );
      })}
    </div>
  );
}
