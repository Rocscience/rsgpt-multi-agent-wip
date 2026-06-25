// hero.ts
import { heroui } from "@heroui/react";

export default heroui({
  themes: {
    light: {
      colors: {
        primary: {
          foreground: "#FFFFFF",
          DEFAULT: "#e35205",
          50: "#FFF4ED",
          100: "#FFE4D4",
          200: "#FFC9A8",
          300: "#FFA770",
          400: "#FF7D38",
          500: "#F65D12",
          600: "#E35205",
          700: "#BC4004",
          800: "#963306",
          900: "#7A2B0A",
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
          50: "#1A0D00",
          100: "#2D1600",
          200: "#4A2500",
          300: "#6B3600",
          400: "#8C4700",
          500: "#BA4100",
          600: "#D35400",
          700: "#E86A1A",
          800: "#F28033",
          900: "#FFAA66",
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