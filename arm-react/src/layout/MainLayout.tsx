import RefreshIcon from "@mui/icons-material/Refresh";
import HomeIcon from "@mui/icons-material/Home";
import HistoryIcon from "@mui/icons-material/History";
import DescriptionIcon from "@mui/icons-material/Description";
import SettingsIcon from "@mui/icons-material/Settings";
import NotificationsIcon from "@mui/icons-material/Notifications";
import {
  AppBar,
  Badge,
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
} from "@mui/material";
import { useIsFetching, useQueryClient } from "@tanstack/react-query";
import {
  Link as RouterLink,
  Outlet,
  useLocation,
  useNavigate,
} from "react-router-dom";
import { useArmSocket } from "../hooks/useArmSocket";
import { useAuth } from "../auth/useAuth";
import { useToast } from "../providers/useToast";
import { labels } from "../labels";
import { useThemeMode } from "../theme/useThemeMode";
import GitHubIcon from "@mui/icons-material/GitHub";

const GITHUB_URL =
  "https://github.com/automatic-ripping-machine/automatic-ripping-machine";

const DRAWER_WIDTH = 240;

const NAV_ITEMS = [
  { label: labels.nav.home, to: "/", icon: HomeIcon },
  { label: labels.nav.history, to: "/history", icon: HistoryIcon },
  { label: labels.nav.logs, to: "/logs", icon: DescriptionIcon },
  { label: labels.nav.settings, to: "/settings", icon: SettingsIcon },
  { label: labels.nav.notifications, to: "/notifications", icon: NotificationsIcon },
];

function isNavActive(pathname: string, to: string): boolean {
  if (to === "/") {
    return pathname === "/";
  }
  return pathname.startsWith(to);
}

export function MainLayout() {
  const { isAuthenticated, logout } = useAuth();
  const { mode, toggleMode } = useThemeMode();
  const { unreadCount } = useToast();
  const socketConnected = useArmSocket(isAuthenticated);
  const theme = useTheme();
  const queryClient = useQueryClient();
  const location = useLocation();
  const navigate = useNavigate();
  const dashboardFetching =
    useIsFetching({ queryKey: ["system", "dashboard"] }) > 0;

  const onRefresh = () => {
    void queryClient.invalidateQueries({ queryKey: ["system", "dashboard"] });
  };

  const showRefresh = isAuthenticated && location.pathname === "/";

  return (
    <Box sx={{ display: "flex" }}>
      <Drawer
        sx={{
          width: DRAWER_WIDTH,
          flexShrink: 0,
          backgroundColor: theme.palette.background.default,
          "& .MuiDrawer-paper": {
            width: DRAWER_WIDTH,
            boxSizing: "border-box",
          },
        }}
        variant="persistent"
        anchor="left"
        open={true}
      >
        <Box sx={{ margin: theme.spacing(2) }}>
          <Box sx={{ display: "flex", alignItems: "center" }}>
            <Typography
              variant="h6"
              component={RouterLink}
              to="/"
              sx={{
                flexGrow: { xs: 0, md: 0 },
                mr: 1,
                color: theme.palette.primary.main,
                textDecoration: "none",
                textShadow: `0 0 2px ${theme.palette.primary.main},
         0 0 4px rgba(0,240,255,0.6);`,
              }}
            >
              {labels.appTitle}
            </Typography>
            <GitHubIcon />
          </Box>
          <Typography variant="body2" sx={{ color: "text.secondary" }}>
            {labels.appSubtitle}
          </Typography>
          <Typography
            variant="body2"
            sx={{ color: "text.secondary", fontSize: "0.75rem" }}
          >
            {labels.appVersion}
          </Typography>
        </Box>
        <Divider />
        <List>
          {NAV_ITEMS.map((item) => {
            const Icon = item.icon;
            return (
              <ListItem key={item.to} disablePadding>
                <ListItemButton
                  component={RouterLink}
                  to={item.to}
                  selected={isNavActive(location.pathname, item.to)}
                >
                  <ListItemIcon>
                    <Icon />
                  </ListItemIcon>
                  <ListItemText>
                    <Typography variant="body2" sx={{ color: "text.secondary" }}>
                      {item.label}
                    </Typography>
                  </ListItemText>
                </ListItemButton>
              </ListItem>
            );
          })}
        </List>
        <Box sx={{ flexGrow: 1 }} />
        <Divider />

        <Box sx={{ p: 2, display: "flex", flexDirection: "column" }}>
          {isAuthenticated ? (
            <Button variant="outlined" onClick={logout}>
              {labels.nav.logout}
            </Button>
          ) : (
            <Button
              variant="outlined"
              onClick={() => {
                navigate("/login");
              }}
            >
              {labels.nav.login}
            </Button>
          )}
        </Box>
      </Drawer>
      <Box
        sx={{
          minHeight: "100vh",
          display: "flex",
          flexGrow: 1,
          flexDirection: "column",
          bgcolor: "background.default",
        }}
      >
        <AppBar position="static" color="default" elevation={1}>
          <Toolbar variant="dense" sx={{ gap: 1 }}>
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
            {isAuthenticated && (
              <IconButton
                color="inherit"
                component={RouterLink}
                to="/notifications"
                aria-label={labels.nav.notifications}
                title={labels.nav.notifications}
              >
                <Badge badgeContent={unreadCount} color="primary" max={99}>
                  <NotificationsIcon />
                </Badge>
              </IconButton>
            )}
            <FormControlLabel
              control={
                <Switch
                  checked={mode === "dark"}
                  onChange={toggleMode}
                  color="default"
                />
              }
              label={labels.nav.darkMode}
              sx={{ mr: 1, ml: 0 }}
            />
            {isAuthenticated && (
              <Box
                title={socketConnected ? "Connected" : "Disconnected"}
                sx={{
                  width: 8,
                  height: 8,
                  borderRadius: "50%",
                  bgcolor: socketConnected ? "success.main" : "text.disabled",
                  flexShrink: 0,
                }}
              />
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
            textAlign: "center",
            typography: "body2",
            color: "text.secondary",
          }}
        >
          <Container maxWidth="md">
            {labels.footer.line}{" "}
            <Link href={GITHUB_URL} target="_blank" rel="noopener noreferrer">
              {labels.footer.github}
            </Link>
          </Container>
        </Box>
      </Box>
    </Box>
  );
}
