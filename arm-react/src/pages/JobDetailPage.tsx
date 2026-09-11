import { useState } from 'react'
import CheckIcon from '@mui/icons-material/Check'
import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  CardHeader,
  CardMedia,
  Chip,
  CircularProgress,
  Container,
  Dialog,
  DialogActions,
  DialogContent,
  DialogContentText,
  DialogTitle,
  Grid,
  LinearProgress,
  Link,
  MenuItem,
  Paper,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  TextField,
  Tooltip,
  Typography,
} from '@mui/material'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link as RouterLink, useNavigate, useParams } from 'react-router-dom'
import {
  abandonJob,
  deleteJob,
  fetchJobDetail,
  fetchJobLogs,
  fetchJobProgress,
  updateJobMetadata,
} from '../api/jobsApi'
import { ApiError } from '../api/http'
import type { JobDetail, JobMetadataUpdate, TrackInfo } from '../api/types'
import { useAuth } from '../auth/useAuth'
import { LogViewer } from '../components/LogViewer'
import { labels } from '../labels'
import { humanizeRelativeTime } from '../utils/humanize'

const POLL_ACTIVE_MS = 30000
const POLL_LOGS_MS = 10000

const VIDEO_TYPES = ['movie', 'series', 'Music', 'unknown'] as const

type MetadataField = 'title' | 'year' | 'video_type' | 'imdb_id' | 'poster_url'

type MetadataFieldErrors = Partial<Record<MetadataField, string>>

interface MetadataFormState {
  title: string
  year: string
  video_type: string
  imdb_id: string
  poster_url: string
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

function jobDisplayTitle(job: JobDetail): string {
  return (
    meaningfulText(job.title_manual) ??
    meaningfulText(job.title) ??
    meaningfulText(job.title_auto) ??
    meaningfulText(job.label) ??
    meaningfulText(job.devpath) ??
    labels.jobs.unnamedJob
  )
}

function statusChipColor(status: string): 'success' | 'error' | 'primary' | 'default' {
  const normalized = status.trim().toLowerCase()
  if (normalized === 'success') {
    return 'success'
  }
  if (normalized === 'fail' || normalized === 'failure' || normalized === 'error') {
    return 'error'
  }
  if (!normalized) {
    return 'default'
  }
  return 'primary'
}

function isFinishedStatus(status: string | null | undefined): boolean {
  const normalized = (status ?? '').trim().toLowerCase()
  return normalized === 'success' || normalized === 'fail'
}

function parseTimestamp(value: string): number {
  const normalized = value.includes('T') ? value : value.replace(' ', 'T')
  return Date.parse(normalized)
}

function formatTimestamp(value: string): string | null {
  if (!meaningfulText(value) || Number.isNaN(parseTimestamp(value))) {
    return null
  }
  return humanizeRelativeTime(value)
}

function formatDuration(job: JobDetail): string | null {
  const jobLength = meaningfulText(job.job_length)
  if (jobLength) {
    return jobLength
  }
  const startMs = meaningfulText(job.start_time) ? parseTimestamp(job.start_time) : Number.NaN
  const stopMs = meaningfulText(job.stop_time) ? parseTimestamp(job.stop_time) : Number.NaN
  if (Number.isNaN(startMs) || Number.isNaN(stopMs) || stopMs <= startMs) {
    return null
  }
  const totalSeconds = Math.round((stopMs - startMs) / 1000)
  const hours = Math.floor(totalSeconds / 3600)
  const minutes = Math.floor((totalSeconds % 3600) / 60)
  const seconds = totalSeconds % 60
  return `${hours}:${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`
}

function parseProgress(progress: string | number | null | undefined): number | null {
  const value = typeof progress === 'number' ? progress : Number.parseFloat(progress ?? '')
  return Number.isFinite(value) && value > 0 ? value : null
}

function isTrue(value: string | undefined): boolean {
  return (value ?? '').trim().toLowerCase() === 'true'
}

function formatTrackLength(value: string): string | null {
  const trimmed = meaningfulText(value)
  if (!trimmed) {
    return null
  }
  if (/^\d{1,2}:\d{2}(:\d{2})?$/.test(trimmed)) {
    return trimmed
  }
  const seconds = Number.parseFloat(trimmed)
  if (!Number.isFinite(seconds)) {
    return trimmed
  }
  const totalSeconds = Math.max(0, Math.round(seconds))
  const hours = Math.floor(totalSeconds / 3600)
  const minutes = Math.floor((totalSeconds % 3600) / 60)
  const remaining = totalSeconds % 60
  if (hours === 0) {
    return `${String(minutes).padStart(2, '0')}:${String(remaining).padStart(2, '0')}`
  }
  return `${hours}:${String(minutes).padStart(2, '0')}:${String(remaining).padStart(2, '0')}`
}

function formatFilesize(value: string): string | null {
  const bytes = Number.parseFloat(value)
  if (!Number.isFinite(bytes) || bytes <= 0) {
    return null
  }
  const units = ['B', 'KB', 'MB', 'GB', 'TB']
  let size = bytes
  let unitIndex = 0
  while (size >= 1024 && unitIndex < units.length - 1) {
    size /= 1024
    unitIndex += 1
  }
  return `${unitIndex === 0 ? String(size) : size.toFixed(1)} ${units[unitIndex]}`
}

function trackStatusColor(track: TrackInfo): 'success' | 'error' | 'default' {
  if (meaningfulText(track.error)) {
    return 'error'
  }
  return isTrue(track.ripped) ? 'success' : 'default'
}

function extractErrorMessage(error: unknown): string | null {
  if (error instanceof ApiError) {
    const bodyError = (error.body as { error?: unknown } | null | undefined)?.error
    if (typeof bodyError === 'string' && bodyError.trim()) {
      return bodyError
    }
    return error.message
  }
  if (error instanceof Error && error.message) {
    return error.message
  }
  return null
}

function isNotFound(error: unknown): boolean {
  return error instanceof ApiError && error.status === 404
}

function jobToForm(job: JobDetail): MetadataFormState {
  return {
    title: meaningfulText(job.title_manual) ?? meaningfulText(job.title) ?? '',
    year: meaningfulText(job.year) ?? '',
    video_type: meaningfulText(job.video_type) ?? '',
    imdb_id: meaningfulText(job.imdb_id) ?? '',
    poster_url: meaningfulText(job.poster_url) ?? '',
  }
}

function buildMetadataPayload(
  form: MetadataFormState,
  current: MetadataFormState,
): JobMetadataUpdate | null {
  const payload: JobMetadataUpdate = {}
  const title = form.title.trim()
  if (title && title !== current.title) {
    payload.title = title
  }
  const year = form.year.trim()
  if (year && year !== current.year) {
    payload.year = year
  }
  const videoType = form.video_type.trim()
  if (videoType && videoType !== current.video_type) {
    payload.video_type = videoType
  }
  const imdbId = form.imdb_id.trim()
  if (imdbId && imdbId !== current.imdb_id) {
    payload.imdb_id = imdbId
  }
  const posterUrl = form.poster_url.trim()
  if (posterUrl && posterUrl !== current.poster_url) {
    payload.poster_url = posterUrl
  }
  return Object.keys(payload).length > 0 ? payload : null
}

function PosterImage({ src, alt }: { src: string; alt: string }) {
  const [failed, setFailed] = useState(false)
  if (failed) {
    return null
  }
  return (
    <CardMedia
      component="img"
      image={src}
      alt={alt}
      onError={() => setFailed(true)}
      sx={{ width: '100%', height: '100%', maxHeight: 480, objectFit: 'contain' }}
    />
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

export function JobDetailPage() {
  const { isAuthenticated } = useAuth()
  const params = useParams()
  const jobId = params.jobId ?? ''
  const navigate = useNavigate()
  const queryClient = useQueryClient()

  const [metadataOpen, setMetadataOpen] = useState(false)
  const [abandonOpen, setAbandonOpen] = useState(false)
  const [deleteOpen, setDeleteOpen] = useState(false)
  const [logOpen, setLogOpen] = useState(false)

  const detailQuery = useQuery({
    queryKey: ['jobs', jobId],
    queryFn: () => fetchJobDetail(jobId),
    enabled: isAuthenticated && jobId !== '',
    retry: (failureCount, error) => !isNotFound(error) && failureCount < 2,
  })

  const job = detailQuery.data
  const finished = job !== undefined && isFinishedStatus(job.status)

  const progressQuery = useQuery({
    queryKey: ['jobs', jobId, 'progress'],
    queryFn: () => fetchJobProgress(jobId),
    enabled: isAuthenticated && jobId !== '' && !finished,
    refetchInterval: POLL_ACTIVE_MS,
  })

  const logsQuery = useQuery({
    queryKey: ['jobs', jobId, 'logs', logOpen],
    queryFn: () => fetchJobLogs(jobId),
    enabled: isAuthenticated && jobId !== '' && logOpen,
    refetchInterval: logOpen && !finished ? POLL_LOGS_MS : false,
    retry: (failureCount, error) => !isNotFound(error) && failureCount < 1,
  })

  const abandonMutation = useMutation({
    mutationFn: () => abandonJob(jobId),
    onSuccess: () => {
      setAbandonOpen(false)
      void queryClient.invalidateQueries({ queryKey: ['jobs'] })
    },
  })

  const deleteMutation = useMutation({
    mutationFn: () => deleteJob(jobId),
    onSuccess: () => {
      setDeleteOpen(false)
      queryClient.removeQueries({ queryKey: ['jobs', jobId] })
      void queryClient.invalidateQueries({ queryKey: ['jobs'] })
      navigate('/history')
    },
  })

  const logContent = logsQuery.data?.content ?? ''

  if (jobId === '' || (detailQuery.isError && isNotFound(detailQuery.error))) {
    return (
      <Container maxWidth="lg">
        <Box sx={{ py: 8, textAlign: 'center' }}>
          <Typography variant="h5" gutterBottom>
            {labels.jobDetail.notFound}
          </Typography>
          <Button component={RouterLink} to="/history" variant="outlined">
            {labels.jobDetail.backToHistory}
          </Button>
        </Box>
      </Container>
    )
  }

  if (!isAuthenticated) {
    return (
      <Container maxWidth="lg">
        <Alert severity="info" sx={{ mt: 2 }}>
          {labels.jobDetail.loginToView}{' '}
          <Link component={RouterLink} to="/login">
            {labels.nav.login}
          </Link>
        </Alert>
      </Container>
    )
  }

  if (detailQuery.isPending || !job) {
    return (
      <Container maxWidth="lg">
        <LinearProgress sx={{ mt: 2 }} />
      </Container>
    )
  }

  if (detailQuery.isError) {
    return (
      <Container maxWidth="lg">
        <Alert
          severity="error"
          sx={{ mt: 2 }}
          action={
            <Button color="inherit" size="small" onClick={() => void detailQuery.refetch()}>
              {labels.jobDetail.retry}
            </Button>
          }
        >
          {labels.jobDetail.loadError}
        </Alert>
      </Container>
    )
  }

  const displayTitle = jobDisplayTitle(job)
  const status = meaningfulText(job.status)
  const disctype = meaningfulText(job.disctype)
  const year = meaningfulText(job.year)
  const drive = meaningfulText(job.devpath)
  const started = formatTimestamp(job.start_time)
  const stopped = formatTimestamp(job.stop_time)
  const duration = formatDuration(job)
  const errorText = meaningfulText(job.errors)
  const posterUrl = meaningfulText(job.poster_url)

  const progress = progressQuery.data
  const percent = parseProgress(progress?.progress ?? job.progress)
  const stage = meaningfulText(progress?.stage) ?? meaningfulText(job.stage)
  const eta = meaningfulText(progress?.eta) ?? meaningfulText(job.eta)
  const progressStatus = meaningfulText(progress?.status) ?? status

  const logsError = logsQuery.isError
    ? isNotFound(logsQuery.error)
      ? 'missing'
      : 'error'
    : null

  return (
    <Container maxWidth="lg">
      <Box sx={{ display: 'flex', alignItems: 'center', flexWrap: 'wrap', gap: 2, mb: 3 }}>
        <Typography variant="h5" component="h1" sx={{ fontWeight: 800 }}>
          {labels.jobDetail.title}
        </Typography>
        <Box sx={{ flexGrow: 1 }} />
        <Button component={RouterLink} to="/history">
          {labels.jobDetail.backToHistory}
        </Button>
      </Box>

      <Card variant="outlined" sx={{ mb: 3, overflow: 'hidden' }}>
        <Grid container>
          {posterUrl && (
            <Grid size={{ xs: 12, sm: 4, md: 3 }}>
              <PosterImage key={posterUrl} src={posterUrl} alt={displayTitle} />
            </Grid>
          )}
          <Grid size={{ xs: 12, sm: posterUrl ? 8 : 12, md: posterUrl ? 9 : 12 }}>
            <CardContent>
              <Box
                sx={{
                  display: 'flex',
                  alignItems: 'flex-start',
                  justifyContent: 'space-between',
                  flexWrap: 'wrap',
                  gap: 1,
                  mb: 2,
                }}
              >
                <Typography variant="h6" sx={{ fontWeight: 600, wordBreak: 'break-word' }}>
                  {displayTitle}
                </Typography>
                <Box sx={{ display: 'flex', gap: 1 }}>
                  {disctype && (
                    <Chip label={disctype} size="small" color="primary" variant="outlined" />
                  )}
                  {status && (
                    <Chip
                      label={status}
                      size="small"
                      color={statusChipColor(status)}
                      variant="outlined"
                    />
                  )}
                </Box>
              </Box>
              <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
                <Row label={labels.jobDetail.year} value={year ?? '—'} />
                <Row label={labels.jobDetail.drive} value={drive ?? '—'} />
                <Row label={labels.jobDetail.started} value={started ?? '—'} />
                <Row label={labels.jobDetail.finished} value={stopped ?? '—'} />
                <Row label={labels.jobDetail.duration} value={duration ?? '—'} />
              </Box>
            </CardContent>
          </Grid>
        </Grid>
      </Card>

      {errorText && (
        <Alert severity="error" sx={{ mb: 3, whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>
          {errorText}
        </Alert>
      )}

      <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1, mb: 3 }}>
        <Button variant="outlined" onClick={() => setMetadataOpen(true)}>
          {labels.jobDetail.editMetadata}
        </Button>
        {!finished && (
          <Button
            variant="outlined"
            color="warning"
            onClick={() => {
              abandonMutation.reset()
              setAbandonOpen(true)
            }}
          >
            {labels.jobDetail.abandon}
          </Button>
        )}
        {finished && (
          <Button
            variant="outlined"
            color="error"
            onClick={() => {
              deleteMutation.reset()
              setDeleteOpen(true)
            }}
          >
            {labels.jobDetail.delete}
          </Button>
        )}
      </Box>

      <Card variant="outlined" sx={{ mb: 3 }}>
        <CardHeader title={labels.jobDetail.progressSection} />
        <CardContent>
          {!finished ? (
            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
              <Row label={labels.jobDetail.status} value={progressStatus ?? '—'} />
              <Row label={labels.jobDetail.stage} value={stage ?? '—'} />
              {percent === null ? (
                <Box>
                  <LinearProgress sx={{ height: 8, borderRadius: 1, mb: 0.5 }} />
                  <Typography variant="caption" color="text.secondary">
                    {labels.jobDetail.progressUnknown}
                  </Typography>
                </Box>
              ) : (
                <Box>
                  <LinearProgress
                    variant="determinate"
                    value={Math.min(100, percent)}
                    color={percent >= 90 ? 'error' : 'primary'}
                    sx={{ height: 8, borderRadius: 1, mb: 0.5 }}
                  />
                  <Typography variant="caption" color="text.secondary">
                    {`${Math.min(100, percent).toFixed(1)}%${
                      eta ? ` · ${labels.jobDetail.eta}: ${eta}` : ''
                    }`}
                  </Typography>
                </Box>
              )}
              <Row label={labels.jobDetail.eta} value={eta ?? '—'} />
            </Box>
          ) : (
            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
              <Row label={labels.jobDetail.status} value={status ?? '—'} />
              <Row label={labels.jobDetail.stage} value={meaningfulText(job.stage) ?? '—'} />
              <Row label={labels.jobDetail.duration} value={duration ?? '—'} />
            </Box>
          )}
        </CardContent>
      </Card>

      {job.tracks !== undefined && job.tracks.length > 0 && (
        <TracksSection tracks={job.tracks} />
      )}

      <Card variant="outlined" sx={{ mb: 3 }}>
        <CardHeader
          title={labels.jobDetail.logSection}
          action={
            <Button size="small" onClick={() => setLogOpen((v) => !v)}>
              {logOpen ? labels.jobDetail.hideLog : labels.jobDetail.viewLog}
            </Button>
          }
        />
        {logOpen && (
          <CardContent>
            {logsError === 'missing' ? (
              <Alert severity="info">{labels.jobDetail.logMissing}</Alert>
            ) : logsError === 'error' ? (
              <Alert severity="error">{labels.jobDetail.logLoadError}</Alert>
            ) : (
              <LogViewer
                content={logContent}
                isLoading={logsQuery.isPending}
                onRefresh={() => void logsQuery.refetch()}
              />
            )}
          </CardContent>
        )}
      </Card>

      {metadataOpen && (
        <MetadataDialog
          jobId={jobId}
          job={job}
          onClose={() => setMetadataOpen(false)}
        />
      )}

      <ConfirmDialog
        open={abandonOpen}
        title={labels.jobDetail.abandonTitle}
        message={labels.jobDetail.abandonMessage}
        confirmLabel={labels.jobDetail.abandon}
        pending={abandonMutation.isPending}
        error={
          abandonMutation.isError
            ? extractErrorMessage(abandonMutation.error) ?? labels.jobDetail.abandonError
            : null
        }
        onConfirm={() => abandonMutation.mutate()}
        onClose={() => setAbandonOpen(false)}
      />

      <ConfirmDialog
        open={deleteOpen}
        title={labels.jobDetail.deleteTitle}
        message={labels.jobDetail.deleteMessage}
        confirmLabel={labels.jobDetail.delete}
        pending={deleteMutation.isPending}
        error={
          deleteMutation.isError
            ? extractErrorMessage(deleteMutation.error) ?? labels.jobDetail.deleteError
            : null
        }
        onConfirm={() => deleteMutation.mutate()}
        onClose={() => setDeleteOpen(false)}
      />
    </Container>
  )
}

function MetadataDialog({
  jobId,
  job,
  onClose,
}: {
  jobId: string
  job: JobDetail
  onClose: () => void
}) {
  const queryClient = useQueryClient()
  const [form, setForm] = useState<MetadataFormState>(() => jobToForm(job))
  const [fieldErrors, setFieldErrors] = useState<MetadataFieldErrors>({})
  const [formError, setFormError] = useState<string | null>(null)

  const mutation = useMutation({
    mutationFn: (payload: JobMetadataUpdate) => updateJobMetadata(jobId, payload),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['jobs'] })
      onClose()
    },
    onError: (error) => {
      const message = extractErrorMessage(error) ?? labels.jobDetail.metadataSaveError
      const match = /^Invalid value for field:\s*(\S+)/.exec(message)
      if (match) {
        const field = match[1] as MetadataField
        if (
          field === 'title' ||
          field === 'year' ||
          field === 'video_type' ||
          field === 'imdb_id' ||
          field === 'poster_url'
        ) {
          const nextErrors: MetadataFieldErrors = {}
          nextErrors[field] = message
          setFieldErrors(nextErrors)
          return
        }
      }
      setFormError(message)
    },
  })

  const current = jobToForm(job)
  const payload = buildMetadataPayload(form, current)

  const updateField = (field: MetadataField, value: string) => {
    setForm((prev) => ({ ...prev, [field]: value }))
  }

  const handleSave = () => {
    setFieldErrors({})
    setFormError(null)
    const year = form.year.trim()
    if (year && !/^\d{1,4}$/.test(year)) {
      setFieldErrors({ year: labels.jobDetail.fieldYearInvalid })
      return
    }
    if (payload) {
      mutation.mutate(payload)
    }
  }

  return (
    <Dialog open onClose={onClose} maxWidth="sm" fullWidth>
      <DialogTitle>{labels.jobDetail.metadataTitle}</DialogTitle>
      <DialogContent>
        {formError && (
          <Alert severity="error" sx={{ mt: 1, mb: 1 }}>
            {formError}
          </Alert>
        )}
        <TextField
          margin="dense"
          label={labels.jobDetail.fieldTitle}
          value={form.title}
          onChange={(event) => updateField('title', event.target.value)}
          fullWidth
          error={Boolean(fieldErrors.title)}
          helperText={fieldErrors.title}
        />
        <TextField
          margin="dense"
          label={labels.jobDetail.fieldYear}
          value={form.year}
          onChange={(event) => updateField('year', event.target.value)}
          fullWidth
          error={Boolean(fieldErrors.year)}
          helperText={fieldErrors.year}
        />
        <TextField
          margin="dense"
          select
          label={labels.jobDetail.fieldVideoType}
          value={form.video_type}
          onChange={(event) => updateField('video_type', event.target.value)}
          fullWidth
          error={Boolean(fieldErrors.video_type)}
          helperText={fieldErrors.video_type}
        >
          {VIDEO_TYPES.map((videoType) => (
            <MenuItem key={videoType} value={videoType}>
              {videoType}
            </MenuItem>
          ))}
        </TextField>
        <TextField
          margin="dense"
          label={labels.jobDetail.fieldImdbId}
          value={form.imdb_id}
          onChange={(event) => updateField('imdb_id', event.target.value)}
          fullWidth
          error={Boolean(fieldErrors.imdb_id)}
          helperText={fieldErrors.imdb_id}
        />
        <TextField
          margin="dense"
          label={labels.jobDetail.fieldPosterUrl}
          value={form.poster_url}
          onChange={(event) => updateField('poster_url', event.target.value)}
          fullWidth
          error={Boolean(fieldErrors.poster_url)}
          helperText={fieldErrors.poster_url}
        />
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose} disabled={mutation.isPending}>
          {labels.jobDetail.cancel}
        </Button>
        <Button
          variant="contained"
          onClick={handleSave}
          disabled={payload === null || mutation.isPending}
          startIcon={mutation.isPending ? <CircularProgress size={16} /> : undefined}
        >
          {labels.jobDetail.save}
        </Button>
      </DialogActions>
    </Dialog>
  )
}

function ConfirmDialog({
  open,
  title,
  message,
  confirmLabel,
  pending,
  error,
  onConfirm,
  onClose,
}: {
  open: boolean
  title: string
  message: string
  confirmLabel: string
  pending: boolean
  error: string | null
  onConfirm: () => void
  onClose: () => void
}) {
  return (
    <Dialog open={open} onClose={pending ? undefined : onClose} maxWidth="xs" fullWidth>
      <DialogTitle>{title}</DialogTitle>
      <DialogContent>
        <DialogContentText>{message}</DialogContentText>
        {error && (
          <Alert severity="error" sx={{ mt: 2 }}>
            {error}
          </Alert>
        )}
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose} disabled={pending}>
          {labels.jobDetail.cancel}
        </Button>
        <Button variant="contained" color="error" onClick={onConfirm} disabled={pending}>
          {confirmLabel}
        </Button>
      </DialogActions>
    </Dialog>
  )
}

function TracksSection({ tracks }: { tracks: TrackInfo[] }) {
  return (
    <Paper variant="outlined" sx={{ mb: 3, overflow: 'hidden' }}>
      <Box sx={{ px: 2, pt: 2 }}>
        <Typography variant="h6" sx={{ fontWeight: 600 }}>
          {labels.jobDetail.tracksSection}
        </Typography>
      </Box>
      <TableContainer>
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>{labels.jobDetail.colTrack}</TableCell>
              <TableCell>{labels.jobDetail.colLength}</TableCell>
              <TableCell>{labels.jobDetail.colAspectRatio}</TableCell>
              <TableCell>{labels.jobDetail.colFps}</TableCell>
              <TableCell>{labels.jobDetail.colMainFeature}</TableCell>
              <TableCell>{labels.jobDetail.colStatus}</TableCell>
              <TableCell>{labels.jobDetail.colFilesize}</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {tracks.map((track) => {
              const trackError = meaningfulText(track.error)
              const statusLabel = meaningfulText(track.status) ?? '—'
              const chip = (
                <Chip
                  label={statusLabel}
                  size="small"
                  variant="outlined"
                  color={trackStatusColor(track)}
                />
              )
              return (
                <TableRow key={track.track_id} hover>
                  <TableCell sx={{ fontWeight: 600 }}>{track.track_number}</TableCell>
                  <TableCell>{formatTrackLength(track.length) ?? '—'}</TableCell>
                  <TableCell>{meaningfulText(track.aspect_ratio) ?? '—'}</TableCell>
                  <TableCell>{meaningfulText(track.fps) ?? '—'}</TableCell>
                  <TableCell>
                    {isTrue(track.main_feature) ? (
                      <CheckIcon fontSize="small" color="success" />
                    ) : (
                      '—'
                    )}
                  </TableCell>
                  <TableCell>
                    {trackError ? (
                      <Tooltip title={trackError} arrow>
                        {chip}
                      </Tooltip>
                    ) : (
                      chip
                    )}
                  </TableCell>
                  <TableCell>{formatFilesize(track.filesize) ?? '—'}</TableCell>
                </TableRow>
              )
            })}
          </TableBody>
        </Table>
      </TableContainer>
    </Paper>
  )
}
