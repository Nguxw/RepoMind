import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: ["Aptos", "Segoe UI", "sans-serif"],
        mono: ["Cascadia Code", "SFMono-Regular", "monospace"]
      },
      colors: {
        paper: "#f4f1e8",
        ink: "#16181d",
        zincLine: "#c7c1b3",
        signal: "#1f8a70",
        citrus: "#d6e356",
        rust: "#b55433",
        basin: "#22577a"
      }
    }
  },
  plugins: []
};

export default config;
