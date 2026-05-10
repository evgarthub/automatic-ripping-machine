import RefreshIcon from '@mui/icons-material/Refresh'
import {
  AppBar,
  Box,
  Container,
  FormControlLabel,
  IconButton,
  Link,
  Switch,
  Toolbar,
  Typography,
} from '@mui/material'
import { useIsFetching, useQueryClient } from '@tanstack/react-query'
import { Link as RouterLink, Outlet, useLocation } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'
import { labels } from '../labels'
import { useThemeMode } from '../theme/ThemeModeContext'

const GITHUB_URL =
  'https://github.com/automatic-ripping-machine/automatic-ripping-machine'

export function MainLayout() {
  const { isAuthenticated, logout } = useAuth()
  const { mode, toggleMode } = useThemeMode()
  const queryClient = useQueryClient()
  const location = useLocation()
  const dashboardFetching =
    useIsFetching({ queryKey: ['system', 'dashboard'] }) > 0

  const onRefresh = () => {
    void queryClient.invalidateQueries({ queryKey: ['system', 'dashboard'] })
  }

  const showRefresh = isAuthenticated && location.pathname === '/'

  return (
    <Box
      sx={{
        minHeight: '100vh',
        display: 'flex',
        flexDirection: 'column',
        bgcolor: 'background.default',
      }}
    >
      <AppBar position="static" color="default" elevation={1}>
        <Toolbar variant="dense" sx={{ gap: 1 }}>
          <Typography
            variant="h6"
            component={RouterLink}
            to="/"
            sx={{
              flexGrow: { xs: 0, md: 0 },
              mr: 2,
              color: 'inherit',
              textDecoration: 'none',
              fontWeight: 700,
            }}
          >
            {labels.appTitle}
          </Typography>
          <Link
            component={RouterLink}
            to="/"
            color="inherit"
            underline="hover"
            sx={{ mr: 2 }}
          >
            {labels.nav.home}
          </Link>
          <Box sx={{ flexGrow: 1 }} />
          {showRefresh && (
            <IconButton
              color="inherit"
              onClick={onRefresh}
              disabled={dashboardFetching}
              aria-label={labels.refresh.ariaLabel}
              title={labels.refresh.label}
            >
              <RefreshIcon />
            </IconButton>
          )}
          <FormControlLabel
            control={
              <Switch
                checked={mode === 'dark'}
                onChange={toggleMode}
                color="default"
              />
            }
            label={labels.nav.darkMode}
            sx={{ mr: 1, ml: 0 }}
          />
          {isAuthenticated ? (
            <Link
              component="button"
              variant="body2"
              color="inherit"
              onClick={logout}
              underline="hover"
              sx={{ cursor: 'pointer', background: 'none', border: 0 }}
            >
              {labels.nav.logout}
            </Link>
          ) : (
            <Link
              component={RouterLink}
              to="/login"
              color="inherit"
              underline="hover"
            >
              {labels.nav.login}
            </Link>
          )}
        </Toolbar>
      </AppBar>

      <Box component="main" sx={{ flex: 1, py: 3 }}>
        <Outlet />
      </Box>

      <Box
        component="footer"
        sx={{
          py: 2,
          textAlign: 'center',
          typography: 'body2',
          color: 'text.secondary',
        }}
      >
        <Container maxWidth="md">
          {labels.footer.line}{' '}
          <Link href={GITHUB_URL} target="_blank" rel="noopener noreferrer">
            {labels.footer.github}
          </Link>
        </Container>
      </Box>
    </Box>
  )
}
