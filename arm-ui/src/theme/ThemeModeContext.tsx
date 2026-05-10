import {
  createTheme,
  ThemeProvider,
  CssBaseline,
} from '@mui/material'
import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
  type ReactNode,
} from 'react'

const STORAGE_KEY = 'arm_spa_dark_mode'

type Mode = 'light' | 'dark'

type ThemeModeContextValue = {
  mode: Mode
  toggleMode: () => void
}

const ThemeModeContext = createContext<ThemeModeContextValue | null>(null)

function readInitialMode(): Mode {
  try {
    const v = localStorage.getItem(STORAGE_KEY)
    if (v === 'light') {
      return 'light'
    }
    if (v === 'dark') {
      return 'dark'
    }
  } catch {
    /* ignore */
  }
  return 'dark'
}

export function ThemeModeProvider({ children }: { children: ReactNode }) {
  const [mode, setMode] = useState<Mode>(readInitialMode)

  const toggleMode = useCallback(() => {
    setMode((prev) => {
      const next = prev === 'dark' ? 'light' : 'dark'
      try {
        localStorage.setItem(STORAGE_KEY, next)
      } catch {
        /* ignore */
      }
      return next
    })
  }, [])

  const theme = useMemo(
    () =>
      createTheme({
        palette: {
          mode,
          primary: { main: mode === 'dark' ? '#90caf9' : '#1976d2' },
        },
      }),
    [mode],
  )

  const value = useMemo(() => ({ mode, toggleMode }), [mode, toggleMode])

  return (
    <ThemeModeContext.Provider value={value}>
      <ThemeProvider theme={theme}>
        <CssBaseline />
        {children}
      </ThemeProvider>
    </ThemeModeContext.Provider>
  )
}

export function useThemeMode(): ThemeModeContextValue {
  const ctx = useContext(ThemeModeContext)
  if (!ctx) {
    throw new Error('useThemeMode must be used within ThemeModeProvider')
  }
  return ctx
}
