import CancelIcon from '@mui/icons-material/Cancel'
import CheckCircleIcon from '@mui/icons-material/CheckCircle'
import InfoOutlinedIcon from '@mui/icons-material/InfoOutlined'
import {
  Alert,
  Box,
  Card,
  CardContent,
  CardHeader,
  Chip,
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
import { fetchActiveJobs, fetchJobProgress } from '../api/jobsApi'
import { fetchSystemDashboard, fetchSystemDrivesAdmin } from '../api/systemApi'
import type { JobSummary, SystemDrive } from '../api/types'
import { useAuth } from '../auth/useAuth'
import { labels } from '../labels'
import { humanizeRelativeTime } from '../utils/humanize'

function pctColor(percent: number): 'error' | 'primary' {
  return percent >= 90 ? 'error' : 'primary'
}

function meaningfulText(value: string | null | undefined): string | null {
  if (!value) {
    return null
  }
  const trimmed = value.trim()
  if (!trimmed || trimmed.toLowerCase() === 'none' || trimmed.toLowerCase() === 'unknown') {
    return null
  }
  return trimmed
}

function jobDisplayTitle(job: JobSummary): string {
  return (
    meaningfulText(job.title_manual) ??
    meaningfulText(job.title) ??
    meaningfulText(job.title_auto) ??
    meaningfulText(job.label) ??
    meaningfulText(job.devpath) ??
    labels.jobs.unnamedJob
  )
}

function parseProgress(progress: string | number | null | undefined): number | null {
  const value = typeof progress === 'number' ? progress : Number.parseFloat(progress ?? '')
  return Number.isFinite(value) && value > 0 ? value : null
}

export function HomePage() {
  const { isAuthenticated } = useAuth()

  const dashboardQuery = useQuery({
    queryKey: ['system', 'dashboard'],
    queryFn: fetchSystemDashboard,
    enabled: isAuthenticated,
  })

  const activeJobsQuery = useQuery({
    queryKey: ['jobs', 'active'],
    queryFn: fetchActiveJobs,
    refetchInterval: 15000,
    enabled: isAuthenticated,
  })

  const drivesQuery = useQuery({
    queryKey: ['system', 'drives'],
    queryFn: fetchSystemDrivesAdmin,
    refetchInterval: 15000,
    enabled: isAuthenticated,
  })

  const d = dashboardQuery.data
  const activeJobs = activeJobsQuery.data ?? []
  const drives = drivesQuery.data ?? []

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

      {isAuthenticated && activeJobsQuery.isError && (
        <Alert severity="error" sx={{ mb: 2 }}>
          {labels.jobs.loadError}
        </Alert>
      )}

      {isAuthenticated && activeJobsQuery.isFetching && !activeJobsQuery.data && (
        <LinearProgress sx={{ mb: 2 }} />
      )}

      {isAuthenticated && activeJobs.length === 0 && (
        <Box
          sx={{
            py: 5,
            mb: 4,
            textAlign: 'center',
            border: 1,
            borderColor: 'divider',
            borderRadius: 1,
          }}
        >
          <Typography color="text.secondary">{labels.home.activeRipsEmpty}</Typography>
        </Box>
      )}

      {activeJobs.length > 0 && (
        <Grid container spacing={2} sx={{ mb: 4 }}>
          {activeJobs.map((job) => (
            <Grid size={{ xs: 12, sm: 6, md: 4 }} key={job.job_id}>
              <ActiveJobCard job={job} />
            </Grid>
          ))}
        </Grid>
      )}

      <Typography variant="h6" gutterBottom>
        {labels.drives.title}
      </Typography>

      {isAuthenticated && drivesQuery.isError && (
        <Alert severity="error" sx={{ mb: 2 }}>
          {labels.drives.loadError}
        </Alert>
      )}

      {isAuthenticated && drivesQuery.isFetching && !drivesQuery.data && (
        <LinearProgress sx={{ mb: 2 }} />
      )}

      {isAuthenticated && drives.length > 0 && (
        <Grid container spacing={2} sx={{ mb: 4 }}>
          {drives.map((drive) => (
            <Grid size={{ xs: 12, sm: 6, md: 4 }} key={drive.drive_id}>
              <DriveCard drive={drive} />
            </Grid>
          ))}
        </Grid>
      )}

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

function ActiveJobCard({ job }: { job: JobSummary }) {
  const progressQuery = useQuery({
    queryKey: ['jobs', job.job_id, 'progress'],
    queryFn: () => fetchJobProgress(job.job_id),
    refetchInterval: 15000,
  })

  const progress = progressQuery.data
  const percent = parseProgress(progress?.progress ?? job.progress)
  const stage = meaningfulText(progress?.stage) ?? meaningfulText(job.stage)
  const eta = meaningfulText(progress?.eta)
  const disctype = meaningfulText(job.disctype)
  const startedAt = meaningfulText(job.start_time)

  return (
    <Box
      component={RouterLink}
      to={`/jobs/${encodeURIComponent(job.job_id)}`}
      sx={{ textDecoration: 'none', color: 'inherit' }}
    >
      <Card variant="outlined" sx={{ height: '100%' }}>
        <CardContent>
          <Box
            sx={{
              display: 'flex',
              alignItems: 'flex-start',
              justifyContent: 'space-between',
              gap: 1,
              mb: 1,
            }}
          >
            <Typography variant="subtitle1" sx={{ fontWeight: 600, wordBreak: 'break-word' }}>
              {jobDisplayTitle(job)}
            </Typography>
            {disctype && <Chip label={disctype} size="small" color="primary" variant="outlined" />}
          </Box>
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
            <Row label={labels.system.path} value={job.devpath} />
            <Row
              label={labels.jobs.started}
              value={startedAt ? humanizeRelativeTime(startedAt) : '—'}
            />
            <Row label={labels.jobs.stage} value={stage ?? '—'} />
            {percent === null ? (
              <Box>
                <LinearProgress sx={{ height: 8, borderRadius: 1, mb: 0.5 }} />
                <Typography variant="caption" color="text.secondary">
                  {labels.jobs.progressUnknown}
                </Typography>
              </Box>
            ) : (
              <Box>
                <LinearProgress
                  variant="determinate"
                  value={Math.min(100, percent)}
                  color={pctColor(percent)}
                  sx={{ height: 8, borderRadius: 1, mb: 0.5 }}
                />
                <Typography variant="caption" color="text.secondary">
                  {`${Math.min(100, percent).toFixed(1)}%${
                    eta ? ` · ${labels.jobs.eta}: ${eta}` : ''
                  }`}
                </Typography>
              </Box>
            )}
          </Box>
        </CardContent>
      </Card>
    </Box>
  )
}

function DriveCard({ drive }: { drive: SystemDrive }) {
  const driveName =
    meaningfulText(drive.name) ??
    meaningfulText(drive.mount) ??
    labels.drives.unnamedDrive
  const driveType = meaningfulText(drive.type)
  const modeText =
    drive.drive_mode === 'manual'
      ? labels.settings.drives.modeManual
      : labels.settings.drives.modeAuto
  const stale = drive.stale === true
  const busy = drive.processing || drive.job_current !== null

  let chipLabel: string = labels.drives.idle
  let chipColor: 'success' | 'warning' | 'default' = 'default'
  if (stale) {
    chipLabel = labels.drives.stale
    chipColor = 'warning'
  } else if (busy) {
    chipLabel = labels.drives.ripping
    chipColor = 'success'
  }

  return (
    <Card variant="outlined" sx={{ height: '100%' }}>
      <CardContent>
        <Box
          sx={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            gap: 1,
          }}
        >
          <Typography variant="subtitle2" sx={{ wordBreak: 'break-word' }}>
            {driveName}
          </Typography>
          <Chip label={chipLabel} size="small" color={chipColor} />
        </Box>
        <Typography variant="caption" color="text.secondary">
          {[driveType ?? labels.drives.typeUnknown, modeText].join(' · ')}
        </Typography>
      </CardContent>
    </Card>
  )
}
