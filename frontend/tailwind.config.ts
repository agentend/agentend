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
        bg: "#0e0e0e",
        sidebar: "#161616",
        surface: "#1a1a1a",
        hover: "#1e1e1e",
        border: "#252525",
        "text-primary": "#e0e0e0",
        "text-secondary": "#999",
        "text-muted": "#666",
        accent: "#fff",
        success: "#34d399",
        warning: "#fbbf24",
        error: "#f87171",
      },
    },
  },
  plugins: [],
};
export default config;
