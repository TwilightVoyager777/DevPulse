import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
    "./contexts/**/*.{js,ts,jsx,tsx,mdx}",
    "./hooks/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: ["var(--font-sans)", "system-ui", "sans-serif"],
        mono: ["var(--font-mono)", "ui-monospace", "monospace"],
      },
      colors: {
        brand: {
          50:  "#f0f4ff",
          100: "#e0eaff",
          400: "#7b96fa",
          500: "#4f6ef7",
          600: "#3b57e8",
          700: "#2d44cc",
          900: "#1a2b7a",
          950: "#0d1640",
        },
      },
    },
  },
  plugins: [],
};

export default config;
