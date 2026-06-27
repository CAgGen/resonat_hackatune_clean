/**
 * Memo · Music Explore — Design Tokens
 * Single source of truth for React and CSS consumers.
 */

export const colors = {
  ink: "#1B1B1B",
  paper: "#E5E1D6",
  red: "#ED2024",
  green: "#189A4C",
  pink: "#F45CA0",
  blue: "#2C5BC7",
  yellow: "#F6B400",
};

export const alpha = {
  textSoft: "rgba(229,225,214,.62)",
  line: "rgba(229,225,214,.16)",
};

export const theme = {
  bg: colors.ink,
  surface: colors.ink,
  stage: colors.ink,
  text: colors.paper,
  textSoft: alpha.textSoft,
  textOnAccentDark: colors.paper,
  textOnAccentLight: colors.ink,
  border: alpha.line,
  accent: colors.red,
  focus: colors.blue,
  danger: colors.red,
  success: colors.green,
};

export const fonts = {
  display: '"Courier Prime", "Courier New", ui-monospace, monospace',
  serif: '"Playfair Display", Georgia, serif',
  hand: '"Caveat", "Segoe Script", cursive',
  sans: '"Courier Prime", "Courier New", ui-monospace, monospace',
};

export const type = {
  displayXl: { size: "96px", line: "0.92", family: fonts.display },
  displayL: { size: "64px", line: "0.95", family: fonts.display },
  displayM: { size: "40px", line: "1.0", family: fonts.display },
  serifXl: {
    size: "48px",
    line: "1.1",
    family: fonts.serif,
    style: "italic",
  },
  serifL: { size: "32px", line: "1.2", family: fonts.serif },
  serifBody: { size: "18px", line: "1.6", family: fonts.serif },
  handL: { size: "32px", line: "1.0", family: fonts.hand },
  handM: { size: "22px", line: "1.1", family: fonts.hand },
  uiL: { size: "16px", line: "1.4", family: fonts.sans },
  uiM: { size: "14px", line: "1.4", family: fonts.sans },
  uiS: {
    size: "12px",
    line: "1.3",
    family: fonts.sans,
    tracking: "0.12em",
    transform: "uppercase",
  },
};

export const space = {
  1: "4px",
  2: "8px",
  3: "12px",
  4: "16px",
  5: "24px",
  6: "32px",
  7: "48px",
  8: "64px",
  9: "96px",
};

export const radius = { sm: "4px", md: "10px", pill: "999px" };

export const shadow = {
  block: `6px 6px 0 0 ${colors.paper}`,
  soft: "0 8px 24px rgba(0,0,0,.45)",
};

export const tokens = {
  colors,
  alpha,
  theme,
  fonts,
  type,
  space,
  radius,
  shadow,
};

export const cssVars = {
  "--ink": colors.ink,
  "--paper": colors.paper,
  "--red": colors.red,
  "--green": colors.green,
  "--pink": colors.pink,
  "--blue": colors.blue,
  "--yellow": colors.yellow,
  "--color-bg": theme.bg,
  "--color-surface": theme.surface,
  "--color-text": theme.text,
  "--color-text-soft": theme.textSoft,
  "--color-border": theme.border,
  "--color-accent": theme.accent,
  "--font-display": fonts.display,
  "--font-serif": fonts.serif,
  "--font-hand": fonts.hand,
  "--font-sans": fonts.sans,
};

export function injectCssVars(target = document.documentElement) {
  Object.entries(cssVars).forEach(([key, value]) =>
    target.style.setProperty(key, value),
  );
}

export default tokens;
