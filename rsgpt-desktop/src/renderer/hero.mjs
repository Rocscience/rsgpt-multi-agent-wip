// hero.mjs
import { heroui } from "@heroui/react";

export default heroui({
  themes: {
    light: {
      colors: {
        primary: {
          foreground: "#FFFFFF",
          DEFAULT: "#ED7433",
        },
        secondary: {
          DEFAULT: "#f0f0f0", // Light grey
          foreground: "#737373", // Dark grey text
        },
        default: {
          50: "#fafafa",
          100: "#f5f5f5", 
          200: "#e5e5e5",
          300: "#d4d4d4",
          400: "#a3a3a3",
          500: "#737373",
          600: "#525252",
          700: "#404040",
          800: "#262626",
          900: "#171717",
        },
        content1: "#ffffff",
        content2: "#fafafa",
        background: "#fafafa",
        foreground: "#383838",
        divider: "#f0f0f0",
      },
    },
    dark: {
      colors: {
        primary: {
          foreground: "#FFFFFF",
          DEFAULT: "#BA4100",
        },
        secondary: {
          DEFAULT: "#333333", // Medium dark grey
          foreground: "#d4d4d4", // Off-white text
        },
        default: {
          50: "#0a0a0a",
          100: "#171717",
          200: "#262626",
          300: "#404040",
          400: "#525252",
          500: "#737373",
          600: "#a3a3a3",
          700: "#d4d4d4",
          800: "#e5e5e5",
          900: "#f5f5f5",
        },
        content1: "#262626",
        content2: "#171717",
        background: "#282828",
        foreground: "#fafafa",
        divider: "#333333",
      },
    },
  },
});

