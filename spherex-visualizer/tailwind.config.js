/** @type {import('tailwindcss').Config} */
module.exports = {
  darkMode: 'class',
  content: [
    "./index.html",
    "./src/**/*.{js,jsx,ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        // Light mode surface colors
        "canvas-bg-light": "#FAF9F6",
        "surface-light": "#FFFFFF",
        "surface-elevated-light": "#F4F4F0",
        "primary-text-light": "#111111",
        "muted-text-light": "#52525B",
        "border-light": "#E4E4E7",
        // Dark mode surface colors
        "canvas-bg-dark": "#0A0A0B",
        "surface-dark": "#121214",
        "border-dark": "#222226",
        "primary-text-dark": "#F4F4F6",
        "muted-text-dark": "#8E8E93",
        // Accent colors (single accent)
        "accent": "#0F4C81",
        // Scientific tokens
        "epoch-cyan": "#06B6D4",
        "epoch-amber": "#F59E0B",
      },
      fontFamily: {
        primary: ["'Plus Jakarta Sans'", "'Geist'", "'Inter'", "sans-serif"],
        mono: ["'JetBrains Mono'", "'Geist Mono'", "monospace"],
        display: ["'Instrument Serif'", "'Newsreader'", "serif"],
      },
      borderWidth: {
        hairline: "1px",
      },
      transitionDuration: {
        DEFAULT: "150",
      },
      transitionTimingFunction: {
        DEFAULT: "cubic-bezier(0.16, 1, 0.3, 1)",
      },
    },
  },
  plugins: [],
};
