import CancelIcon from '@mui/icons-material/Cancel'
import CheckCircleIcon from '@mui/icons-material/CheckCircle'
import InfoOutlinedIcon from '@mui/icons-material/InfoOutlined'
import {
  Alert,
  Box,
  Card,
  CardContent,
  CardHeader,
  Container,
  Grid,
  IconButton,
  LinearProgress,
  Link,
  Tooltip,
  Typography,
} from '@mui/material'
import { useQuery } from '@tanstack/react-query'
import { Link as RouterLink } from 'react-router-dom'
import { fetchSystemDashboard } from '../api/systemApi'
import { useAuth } from '../auth/AuthContext'
import { labels } from '../labels'

function pctColor(percent: number): 'error' | 'primary' {
  return percent >= 90 ? 'error' : 'primary'
}

export function HomePage() {
  const { isAuthenticated } = useAuth()

  const dashboardQuery = useQuery({
    queryKey: ['system', 'dashboard'],
    queryFn: fetchSystemDashboard,
    enabled: isAuthenticated,
  })

  const d = dashboardQuery.data

  return (
    <Container maxWidth="lg">
      <Box sx={{ textAlign: 'center', mb: 4 }}>
        <Typography variant="h3" component="h1" gutterBottom sx={{ fontWeight: 800 }}>
          {labels.appTitle}
        </Typography>
        <Typography variant="h6" color="text.secondary" gutterBottom>
          {labels.appSubtitle}
        </Typography>
        <Typography variant="h5" sx={{ mt: 3 }}>
          {labels.home.welcome}
        </Typography>
      </Box>

      <Typography variant="h6" gutterBottom>
        {labels.home.activeRips}
      </Typography>
      <Typography color="text.secondary" sx={{ mb: 4 }}>
        {labels.home.activeRipsEmpty}
      </Typography>

      <Typography variant="h6" gutterBottom>
        {labels.home.systemInformation}
      </Typography>

      {!isAuthenticated && (
        <Alert severity="info" sx={{ mb: 2 }}>
          {labels.home.loginToViewSystem}{' '}
          <Link component={RouterLink} to="/login">
            {labels.nav.login}
          </Link>
        </Alert>
      )}

      {isAuthenticated && dashboardQuery.isError && (
        <Alert severity="error" sx={{ mb: 2 }}>
          {labels.home.loadError}
        </Alert>
      )}

      {isAuthenticated && d && (
        <Grid container spacing={2}>
          <Grid size={{ xs: 12, md: 4 }}>
            <Card variant="outlined">
              <CardHeader title={labels.system.cardTitle} />
              <CardContent>
                <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
                  <Row label={labels.system.name} value={d.server.name} />
                  <Row label={labels.system.description} value={d.server.description} />
                  <Row label={labels.system.cpu} value={d.server.cpu} />
                  <Row
                    label={labels.system.cpuTemp}
                    value={`${d.cpu_temp_c}°C`}
                  />
                  <Typography variant="body2" color="text.secondary">
                    {labels.system.usage}
                  </Typography>
                  <LinearProgress
                    variant="determinate"
                    value={Math.min(100, d.cpu_percent)}
                    color={pctColor(d.cpu_percent)}
                    sx={{ height: 8, borderRadius: 1 }}
                  />
                  <Typography variant="caption" color="text.secondary">
                    {d.cpu_percent.toFixed(1)}%
                  </Typography>
                </Box>
              </CardContent>
            </Card>
          </Grid>

          <Grid size={{ xs: 12, md: 4 }}>
            <Card variant="outlined">
              <CardHeader title={labels.system.memoryTitle} />
              <CardContent>
                <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
                  <Row
                    label={labels.system.total}
                    value={`${d.memory.total_gb} GB`}
                  />
                  <Row
                    label={labels.system.free}
                    value={`${d.memory.free_gb} GB`}
                  />
                  <Row
                    label={labels.system.used}
                    value={`${d.memory.used_gb} GB`}
                  />
                  <Typography variant="body2" color="text.secondary">
                    {labels.system.usage}
                  </Typography>
                  <LinearProgress
                    variant="determinate"
                    value={Math.min(100, d.memory.percent)}
                    color="primary"
                    sx={{ height: 8, borderRadius: 1 }}
                  />
                  <Typography variant="caption" color="text.secondary">
                    {d.memory.percent.toFixed(1)}%
                  </Typography>
                </Box>
              </CardContent>
            </Card>
          </Grid>

          <Grid size={{ xs: 12, md: 4 }}>
            <Card variant="outlined">
              <CardHeader title={labels.system.storageTitle} />
              <CardContent>
                <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                  <StorageBlock
                    title={labels.system.transcode}
                    path={d.storage.transcode.path}
                    freeGb={d.storage.transcode.free_gb}
                    pct={d.storage.transcode.percent_used}
                  />
                  <StorageBlock
                    title={labels.system.completed}
                    path={d.storage.completed.path}
                    freeGb={d.storage.completed.free_gb}
                    pct={d.storage.completed.percent_used}
                  />
                </Box>
              </CardContent>
            </Card>
          </Grid>

          <Grid size={{ xs: 12 }}>
            <Card variant="outlined">
              <CardHeader title={labels.system.hwTitle} titleTypographyProps={{ textAlign: 'center' }} />
              <CardContent>
                <Box
                  sx={{
                    display: 'flex',
                    flexDirection: { xs: 'column', sm: 'row' },
                    gap: 2,
                    justifyContent: 'center',
                    alignItems: 'center',
                  }}
                >
                  <HwRow
                    label={labels.system.intelQsv}
                    ok={d.hw_support.intel}
                  />
                  <HwRow
                    label={labels.system.nvenc}
                    ok={d.hw_support.nvidia}
                  />
                  <HwRow label={labels.system.amdVcn} ok={d.hw_support.amd} />
                </Box>
              </CardContent>
            </Card>
          </Grid>
        </Grid>
      )}

      {isAuthenticated && dashboardQuery.isFetching && !dashboardQuery.data && (
        <LinearProgress sx={{ mt: 2 }} />
      )}
    </Container>
  )
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <Box>
      <Typography variant="caption" color="text.secondary">
        {label}
      </Typography>
      <Typography variant="body2">{value}</Typography>
    </Box>
  )
}

function StorageBlock({
  title,
  path,
  freeGb,
  pct,
}: {
  title: string
  path: string
  freeGb: number
  pct: number
}) {
  return (
    <Box>
      <Typography variant="subtitle2" gutterBottom>
        {title}
      </Typography>
      <LinearProgress
        variant="determinate"
        value={Math.min(100, pct)}
        color={pctColor(pct)}
        sx={{ height: 8, borderRadius: 1, mb: 0.5 }}
      />
      <Typography
        variant="caption"
        color="text.secondary"
        sx={{ display: 'block' }}
      >
        {labels.system.freeSpace}: {freeGb} GB
      </Typography>
      <Typography
        variant="caption"
        color="text.secondary"
        sx={{ wordBreak: 'break-all' }}
      >
        {labels.system.path}: {path}
      </Typography>
    </Box>
  )
}

function HwRow({ label, ok }: { label: string; ok: boolean }) {
  return (
    <Box
      sx={{
        display: 'flex',
        flexDirection: 'row',
        alignItems: 'center',
        gap: 1,
      }}
    >
      {ok ? (
        <CheckCircleIcon color="success" fontSize="small" />
      ) : (
        <CancelIcon color="error" fontSize="small" />
      )}
      <Typography variant="body2">{label}</Typography>
      <Tooltip title={labels.system.hwInfoTooltip}>
        <IconButton size="small" aria-label="info">
          <InfoOutlinedIcon fontSize="small" />
        </IconButton>
      </Tooltip>
    </Box>
  )
}
