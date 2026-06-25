import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./src/renderer/**/*.{js,ts,jsx,tsx}",
    "./node_modules/@heroui/theme/dist/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        primary: {
          foreground: "#FFFFFF",
          DEFAULT: "#E35205",
        },
      },
    },
  },
  darkMode: "class",
  plugins: [],
};

export default config;

