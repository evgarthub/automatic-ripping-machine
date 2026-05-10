import RefreshIcon from '@mui/icons-material/Refresh'
import {
  AppBar,
  Box,
  Container,
  FormControlLabel,
  IconButton,
  Button,
  Link,
  Switch,
  Toolbar,
  Typography,
  Drawer,
  useTheme,
  Divider,
  List,
  ListItem,
  ListItemButton,
  ListItemIcon,
  ListItemText,
} from '@mui/material'
import { useIsFetching, useQueryClient } from '@tanstack/react-query'
import { Link as RouterLink, Outlet, useLocation, useNavigate } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'
import { labels } from '../labels'
import { useThemeMode } from '../theme/ThemeModeContext'
import InboxIcon from '@mui/icons-material/MoveToInbox';
import MailIcon from '@mui/icons-material/Mail';

const GITHUB_URL =
  'https://github.com/automatic-ripping-machine/automatic-ripping-machine'

const DRAWER_WIDTH = 240;

export function MainLayout() {
  const { isAuthenticated, logout } = useAuth()
  const { mode, toggleMode } = useThemeMode()
  const theme = useTheme();
  const queryClient = useQueryClient()
  const location = useLocation()
  const navigate = useNavigate()
  const dashboardFetching =
    useIsFetching({ queryKey: ['system', 'dashboard'] }) > 0

  const onRefresh = () => {
    void queryClient.invalidateQueries({ queryKey: ['system', 'dashboard'] })
  }

  const showRefresh = isAuthenticated && location.pathname === '/'

  return (
    <Box>
      <Drawer
        sx={{
          width: DRAWER_WIDTH,
          flexShrink: 0,
          '& .MuiDrawer-paper': {
            width: DRAWER_WIDTH,
            boxSizing: 'border-box',
          },
        }}
        variant="persistent"
        anchor="left"
        open={true}
      >
        <Divider />
        <List>
          {['Inbox', 'Starred', 'Send email', 'Drafts'].map((text, index) => (
            <ListItem key={text} disablePadding>
              <ListItemButton>
                <ListItemIcon>
                  {index % 2 === 0 ? <InboxIcon /> : <MailIcon />}
                </ListItemIcon>
                <ListItemText primary={text} />
              </ListItemButton>
            </ListItem>
          ))}
        </List>
        <Divider />
        <List>
          {['All mail', 'Trash', 'Spam'].map((text, index) => (
            <ListItem key={text} disablePadding>
              <ListItemButton>
                <ListItemIcon>
                  {index % 2 === 0 ? <InboxIcon /> : <MailIcon />}
                </ListItemIcon>
                <ListItemText primary={text} />
              </ListItemButton>
            </ListItem>
          ))}
        </List>
      </Drawer>
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
              <Button
                variant='outlined'
                onClick={logout}
              >
                {labels.nav.logout}
              </Button>
            ) : (
              <Button
                variant='outlined'
                onClick={() => {
                  navigate('/login')
                }}
              >
                {labels.nav.login}
              </Button>
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
    </Box>

  )
}
