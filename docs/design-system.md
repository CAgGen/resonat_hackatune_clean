# Memo · Music Explore — Design System

A design system for a **music exploration & note-taking app**. The visual language fuses two references:

- **Fig 1 ("Broken" display type):** heavy, chunky, playful display lettering in bold primary colors on near-black.
- **Fig 2 (editorial portfolio):** warm cream paper, refined italic serif, hand-drawn warmth, a single terracotta-red accent.

The result: a **paper-warm canvas** with **loud, candy-bright accents** and **two voices of type** — a typewriter monospace that shouts and carries the UI, and an elegant serif that whispers in editorial headers and quotes.

> This document is the source of truth for implementation (CodeX). Tokens are listed as CSS custom properties; copy them verbatim.

---

## 1. Design Principles

1. **Paper first, color loud.** Default surfaces are warm cream. Color arrives in confident, full-saturation blocks — never timid tints.
2. **Two type voices, clear jobs.** Mono (typewriter) = identity, big moments, UI, body, labels & tags. Serif = editorial reading & quotes. Never blur their roles.
3. **Blocky over rounded.** Shapes echo the Broken letterforms: generous, weighty, slightly imperfect. Big radii on tags, near-square on cards.
4. **Contrast is the system.** Cream/ink and color/cream do the heavy lifting. Avoid gray-on-gray subtlety.
5. **Playful, not chaotic.** One accent dominates a view; others support. Don't paint the rainbow on every screen.

---

## 2. Color Tokens

The palette is **exactly the 7 colors sampled from the "Broken" specimen (Fig 1)** — nothing else. Two neutrals (charcoal + cream) and five bold accents.

### Neutrals

| Token | Hex | Use |
|---|---|---|
| `--ink` | `#1B1B1B` | Charcoal background ("stage"), primary text on cream |
| `--paper` | `#E5E1D6` | Cream surfaces, primary text on charcoal |

### Bold accents

| Token | Hex | Personality |
|---|---|---|
| `--red` | `#ED2024` | Energy, "now playing", alerts |
| `--green` | `#189A4C` | Discover, go, genre tag |
| `--pink` | `#F45CA0` | Highlights, moods, playful tags |
| `--blue` | `#2C5BC7` | Links, info, secondary actions, the "CS" badge |
| `--yellow` | `#F6B400` | Badges, the "Bold" sticker |

### Semantic mapping

**Dark theme (default).** The whole product sits on the specimen's charcoal-black; cream is the text/ink. Accents pop on black exactly as in the original poster.

```css
:root {
  /* neutrals — the only two non-accent colors */
  --color-bg:        #1B1B1B;  /* charcoal-black — global background */
  --color-surface:   #1B1B1B;  /* same black; separate cards with cream hairlines, not new tints */
  --color-stage:     #1B1B1B;  /* hero / player share the same black */
  --color-text:      #E5E1D6;  /* cream text */
  --color-text-onstage: #E5E1D6;
  --color-border:    rgba(229,225,214,.16);  /* cream hairlines on black */

  /* accents (the five Broken colors) */
  --color-accent-red:    #ED2024;
  --color-accent-green:  #189A4C;
  --color-accent-pink:   #F45CA0;
  --color-accent-blue:   #2C5BC7;
  --color-accent-yellow: #F6B400;

  /* default brand accent — pick one of the five; red leads */
  --color-accent: #ED2024;

  /* states (reuse accents, no new hexes) */
  --color-focus:   #2C5BC7;
  --color-danger:  #ED2024;
  --color-success: #189A4C;
}
```

> **Strict palette:** only these 7 hex values may be used. No gray tints, no colored shadows, no terracotta. On the black canvas, quiet text and hairlines are **cream at reduced opacity** (e.g. `rgba(229,225,214,.62)` for secondary text, `rgba(229,225,214,.16)` for dividers) — never a new color. Block shadows are cream offsets, not gray blur.

**Pairing rules**
- Text on `--yellow`, `--pink`, `--paper` → `--ink`.
- Text on `--red`, `--green`, `--blue`, `--ink` (the black canvas) → `--paper`.
- One bold accent leads per view; rotate accents by section/genre, not within a single component cluster.

---

## 3. Typography

**Two families**, both on Google Fonts (free) — exactly the two used in `memo.html`. A typewriter monospace (Courier Prime) carries identity, big moments, UI, body and labels; an editorial serif (Playfair Display) carries headers and quotes. `--font-display` and `--font-sans` are the same monospace family, kept as separate roles.

```html
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Courier+Prime:ital,wght@0,400;0,700;1,400;1,700&family=Playfair+Display:ital,wght@0,400;0,600;1,400;1,600&display=swap" rel="stylesheet">
```

| Role | Family | Token | Notes |
|---|---|---|---|
| **Display** (Broken substitute) | Courier Prime (700) | `--font-display` | Typewriter monospace, all-caps, big. Identity, hero, section shouts. |
| **Editorial serif** | Playfair Display | `--font-serif` | Italic for emotive headers & quotes; roman for long reads. |
| **UI / body / labels** | Courier Prime | `--font-sans` | Typewriter monospace. Buttons, metadata, captions, tags, margin notes. |

```css
:root {
  --font-display: "Courier Prime", "Courier New", ui-monospace, monospace;
  --font-serif:   "Playfair Display", Georgia, serif;
  --font-sans:    "Courier Prime", "Courier New", ui-monospace, monospace;
}
```

### Type scale

| Token | Size / line-height | Family | Usage |
|---|---|---|---|
| `--t-display-xl` | 96px / 0.92 | display | Hero word ("EXPLORE") |
| `--t-display-l` | 64px / 0.95 | display | Page titles |
| `--t-display-m` | 40px / 1.0 | display | Section shouts |
| `--t-serif-xl` | 48px / 1.1 (italic) | serif | Editorial / quote headers |
| `--t-serif-l` | 32px / 1.2 | serif | Sub-heads, track titles in reader |
| `--t-serif-body` | 18px / 1.6 | serif | Long-form memo reading |
| `--t-ui-l` | 16px / 1.4 | sans | Buttons, list titles |
| `--t-ui-m` | 14px / 1.4 | sans | Metadata, captions |
| `--t-ui-s` | 12px / 1.3 | sans | Overlines (uppercase, +0.12em tracking) |

**Tracking:** display `-0.01em`; overlines `+0.12em` uppercase; serif italic default.

---

## 4. Spacing, Radius, Elevation

```css
:root {
  /* 4px base scale */
  --space-1: 4px;  --space-2: 8px;  --space-3: 12px; --space-4: 16px;
  --space-5: 24px; --space-6: 32px; --space-7: 48px; --space-8: 64px; --space-9: 96px;

  /* radius — blocky, not soft */
  --radius-sm: 4px;     /* inputs, small cards */
  --radius-md: 10px;    /* cards */
  --radius-pill: 999px; /* tags, "Bold" stickers */

  /* borders — chunky like Broken strokes */
  --border-thin: 1px solid var(--color-border);
  --border-bold: 2.5px solid var(--color-text);

  /* elevation — flat, ink-based, no blurry gray shadows */
  --shadow-block: 6px 6px 0 0 var(--color-text); /* hard offset block shadow */
  --shadow-soft: 0 8px 24px rgba(26,25,22,.10);
}
```

**Grid:** 12-col, 72px max gutter, content max-width 1200px. Cards snap to a masonry-ish explore grid.

---

## 5. Components

### Buttons
- **Primary:** `--ink` fill, `--paper` text, `--radius-pill`, optional `--shadow-block`. Hover: shift to accent fill (`--red`/`--green` per context).
- **Accent sticker button:** `--yellow` fill, `--ink` text, pill, slight rotation (`-3deg`) — the "Bold"/"Play" sticker from Fig 1.
- **Ghost:** transparent, `--border-bold`, `--ink` text.

### Tags / Chips (mood & genre)
- Pill, mono (`--font-sans`, `--t-ui-m`), colored fill rotating accents. e.g. `#indie` pink, `#focus` green, `#latenight` blue.

### Cards (track / album / memo)
- `--paper` (cream) surface, `--radius-md`, `--border-thin` (charcoal hairline) or `--shadow-block` for featured.
- Cover art square. Title in `--font-serif` (`--t-serif-l`), artist in `--font-sans` (`--t-ui-m`).
- Featured card may flip to a bold accent background with `--paper` text.

### Player bar (the "stage")
- Full-width `--color-stage` (ink) bar. Track title `--font-display` small-caps feel, scrubber in `--red`.

### Memo / note block
- Cream paper card. Body in `--font-serif` `--t-serif-body`. User's aside in `--font-sans` (or `--font-serif` italic), set in `--red` (or the view's lead accent) in the margin or as a pull-quote.

### Hero / section header
- Giant `--font-display` word, optionally with one letter knocked out in an accent block (echoing Fig 1's multicolor letters). Supporting line in `--font-serif` italic.

---

## 6. Motion

Keep it tactile and snappy.
- Hover lift on cards: `translateY(-2px)`, block shadow grows to `8px 8px`. 120ms ease-out.
- Sticker buttons wiggle ±2deg on hover.
- Page section reveals: fade + 12px rise, 240ms.
- Respect `prefers-reduced-motion`.

---

## 7. Accessibility

- Body text contrast ≥ 4.5:1 — use `--paper` (cream) on the black canvas and on red/green/blue; use `--ink` on light accents (yellow, pink). Quiet text is cream at reduced opacity, never a new gray.
- Don't rely on accent color alone to convey genre/state; always pair with a label.
- Focus ring: 2px `--color-focus` (blue) offset 2px, visible on all interactive elements.
- Min tap target 44×44px.

---

## 8. Do / Don't

**Do**
- Let the black canvas breathe; surround loud color with negative space.
- Assign one lead accent per view and rotate by genre.
- Mix the two type voices with their assigned jobs.

**Don't**
- Don't use soft drop shadows everywhere — prefer flat cream block shadows on black.
- Don't set long body copy in the display weight (display is an accent only).
- Don't put more than ~3 bold accents in one viewport.
- Don't round everything; keep cards blocky.

---

## 9. Using in React

This markdown is documentation — it is **not** directly importable into React. Import the tokens from **`tokens.js`** (shipped alongside this doc) instead.

```jsx
import { colors, fonts, theme, type, injectCssVars } from "./tokens";

// Option A — CSS custom properties (recommended). Call once at app start,
// then use var(--…) anywhere, including the preview's stylesheet.
injectCssVars(); // sets --ink, --paper, --red … on :root

// Option B — inline style objects straight from the token map.
function PlayButton({ children }) {
  return (
    <button
      style={{
        fontFamily: fonts.sans,
        fontWeight: 700,
        background: colors.yellow,   // "Bold" sticker yellow
        color: colors.ink,
        border: "none",
        borderRadius: 999,
        padding: "13px 26px",
        cursor: "pointer",
      }}
    >
      {children}
    </button>
  );
}

// Dark canvas wrapper
function AppShell({ children }) {
  return (
    <div style={{ background: theme.bg, color: theme.text, minHeight: "100vh" }}>
      {children}
    </div>
  );
}
```

`tokens.js` exports: `colors`, `alpha`, `theme`, `fonts`, `type`, `space`, `radius`, `shadow`, plus `cssVars` and `injectCssVars()`. Everything resolves to the same 7 hex values defined above. Load the fonts via the Google Fonts `<link>` from §3 in your `index.html` (or import them in CSS).
