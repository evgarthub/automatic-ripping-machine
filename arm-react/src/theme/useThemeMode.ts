import { createContext, useContext } from "react";

export type Mode = "light" | "dark";

export type ThemeModeContextValue = {
  mode: Mode;
  toggleMode: () => void;
};

export const ThemeModeContext = createContext<ThemeModeContextValue | null>(
  null,
);

export function useThemeMode(): ThemeModeContextValue {
  const ctx = useContext(ThemeModeContext);
  if (!ctx) {
    throw new Error("useThemeMode must be used within ThemeModeProvider");
  }
  return ctx;
}
