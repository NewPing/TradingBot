import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        bg: {
          DEFAULT: "#0a0a0a",
          sidebar: "#0d0d0d",
        },
        surface: {
          DEFAULT: "#141414",
          2: "#1c1c1c",
        },
        active: "#1a1a1a",
        border: {
          DEFAULT: "#262626",
          subtle: "#1f1f1f",
        },
        text: {
          1: "#ededed",
          2: "#a1a1aa",
          3: "#71717a",
        },
        pos: "#22c55e",
        neg: "#ef4444",
        warn: "#f59e0b",
        info: "#38bdf8",
      },
      fontFamily: {
        mono: ["ui-monospace", "SFMono-Regular", "Menlo", "Monaco", "Consolas", "monospace"],
      },
      borderRadius: {
        DEFAULT: "6px",
        md: "8px",
        lg: "10px",
      },
    },
  },
  plugins: [],
};

export default config;
