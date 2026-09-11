import { createTheme, ThemeProvider, CssBaseline } from "@mui/material";
import { useCallback, useMemo, useState, type ReactNode } from "react";
import { ThemeModeContext, type Mode } from "./useThemeMode";

const STORAGE_KEY = "arm_spa_dark_mode";

function readInitialMode(): Mode {
  try {
    const v = localStorage.getItem(STORAGE_KEY);
    if (v === "light") {
      return "light";
    }
    if (v === "dark") {
      return "dark";
    }
  } catch {
    /* ignore */
  }
  return "dark";
}

export function ThemeModeProvider({ children }: { children: ReactNode }) {
  const [mode, setMode] = useState<Mode>(readInitialMode);

  const toggleMode = useCallback(() => {
    setMode((prev) => {
      const next = prev === "dark" ? "light" : "dark";
      try {
        localStorage.setItem(STORAGE_KEY, next);
      } catch {
        /* ignore */
      }
      return next;
    });
  }, []);

  const theme = useMemo(
    () =>
      createTheme({
        palette: {
          mode,
          ...(mode === "dark" && {
            primary: { main: "#8ed5ff" },
            secondary: { main: "#bec6e0" },
            tertiary: { main: "#c5c9ff" },
            error: { main: "#ffb4ab" },
            background: { default: "#081425", paper: "#152031" },
            surface: "#081425",
          }),
          ...(mode === "light" && {
            primary: { main: "#0061a4" },
            secondary: { main: "#1e3a5f" },
            error: { main: "#b3261e" },
            background: { default: "#fefbff", paper: "#fffbfe" },
          }),
        },
        typography: {
          fontFamily: "Inter, sans-serif",
          body2: {
            fontFamily: "JetBrains Mono, monospace",
          },
        },
        components: {
          MuiButton: {
            styleOverrides: {
              root: {
                textTransform: "uppercase",
                fontWeight: 600,
                fontSize: "12px",
                letterSpacing: "0.05em",
                fontFamily: "JetBrains Mono, monospace",
                padding: "8px 16px",
                borderRadius: "4px",
                transition: "all 200ms ease-in-out",
                "&:active": {
                  transform: "scale(0.95)",
                },
              },
            },
            variants: [
              {
                props: { variant: "contained", color: "error" },
                style: {
                  backgroundColor: "#ffb4ab",
                  color: "#690005",
                  "&:hover": {
                    backgroundColor: "#ffb4ab",
                    filter: "brightness(1.1)",
                  },
                },
              },
              {
                props: { variant: "outlined", color: "primary" },
                style: {
                  backgroundColor: "#040e1f",
                  color: "#8ed5ff",
                  borderColor: "#8ed5ff",
                  border: "1px solid #8ed5ff",
                  "&:hover": {
                    backgroundColor: "#8ed5ff",
                    color: "#081425",
                    borderColor: "#8ed5ff",
                  },
                },
              },
              {
                props: { variant: "outlined" },
                style: {
                  backgroundColor: "#040e1f",
                  color: "#d8e3fb",
                  borderColor: "#87929a",
                  border: "1px solid #87929a",
                  "&:hover": {
                    backgroundColor: "#152031",
                    borderColor: "#87929a",
                  },
                },
              },
            ],
          },
        },
      }),
    [mode],
  );

  const value = useMemo(() => ({ mode, toggleMode }), [mode, toggleMode]);

  return (
    <ThemeModeContext.Provider value={value}>
      <ThemeProvider theme={theme}>
        <CssBaseline />
        {children}
      </ThemeProvider>
    </ThemeModeContext.Provider>
  );
}
