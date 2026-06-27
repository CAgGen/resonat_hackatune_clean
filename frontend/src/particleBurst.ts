// Self-contained heart "like" particle burst (ported from the music-cards
// reference, but with inline styles so it needs no external CSS). Respects
// prefers-reduced-motion.
export function particleBurst(x: number, y: number, color = "#ED2024") {
  if (typeof document === "undefined") return;
  if (window.matchMedia?.("(prefers-reduced-motion: reduce)").matches) return;

  const N = 16;
  for (let i = 0; i < N; i++) {
    const p = document.createElement("div");
    const size = 4 + Math.random() * 5;
    Object.assign(p.style, {
      position: "fixed",
      left: `${x}px`,
      top: `${y}px`,
      width: `${size}px`,
      height: `${size}px`,
      borderRadius: "50%",
      background: color,
      pointerEvents: "none",
      zIndex: "30000",
      willChange: "transform, opacity",
    });
    document.body.appendChild(p);

    const angle = (i / N) * Math.PI * 2 + Math.random() * 0.5;
    const dist = 24 + Math.random() * 34;
    const dx = Math.cos(angle) * dist;
    const dy = Math.sin(angle) * dist;
    const duration = 550 + Math.random() * 350;

    p.animate(
      [
        { transform: "translate(-50%,-50%) translate(0,0) scale(1)", opacity: 1 },
        {
          transform: `translate(-50%,-50%) translate(${dx}px,${dy + 10}px) scale(0)`,
          opacity: 0,
        },
      ],
      { duration, easing: "cubic-bezier(.18,.7,.3,1)", fill: "forwards" },
    );
    window.setTimeout(() => p.remove(), duration + 60);
  }
}
