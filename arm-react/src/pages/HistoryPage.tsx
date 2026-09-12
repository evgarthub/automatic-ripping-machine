import { useEffect, useState } from 'react'
import type { MouseEvent } from 'react'
import {
  Alert,
  Box,
  Button,
  Chip,
  Container,
  Link,
  MenuItem,
  Pagination,
  Paper,
  Skeleton,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  TextField,
  ToggleButton,
  ToggleButtonGroup,
  Typography,
} from '@mui/material'
import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { Link as RouterLink, useNavigate } from 'react-router-dom'
import { fetchJobsHistory } from '../api/jobsApi'
import type { JobStatusFilter } from '../api/jobsApi'
import type { JobSummary } from '../api/types'
import { useAuth } from '../auth/useAuth'
import { labels } from '../labels'
import { humanizeRelativeTime } from '../utils/humanize'

type StatusToggle = 'all' | JobStatusFilter

const PER_PAGE_OPTIONS = [25, 50, 100] as const
const SEARCH_DEBOUNCE_MS = 400
const SKELETON_ROWS = 8

function isStatusToggle(value: unknown): value is StatusToggle {
  return value === 'all' || value === 'active' || value === 'success' || value === 'fail'
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
  const base =
    meaningfulText(job.title_manual) ??
    meaningfulText(job.title) ??
    meaningfulText(job.title_auto) ??
    meaningfulText(job.label) ??
    meaningfulText(job.devpath) ??
    labels.jobs.unnamedJob
  const year = meaningfulText(job.year)
  return year ? `${base} (${year})` : base
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

function formatDuration(job: JobSummary): string | null {
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

export function HistoryPage() {
  const { isAuthenticated } = useAuth()
  const navigate = useNavigate()

  const [statusFilter, setStatusFilter] = useState<StatusToggle>('all')
  const [searchInput, setSearchInput] = useState('')
  const [search, setSearch] = useState('')
  const [page, setPage] = useState(1)
  const [perPage, setPerPage] = useState<number>(25)

  useEffect(() => {
    const timer = window.setTimeout(() => {
      setSearch(searchInput.trim())
      setPage(1)
    }, SEARCH_DEBOUNCE_MS)
    return () => {
      window.clearTimeout(timer)
    }
  }, [searchInput])

  const statusParam: JobStatusFilter | undefined =
    statusFilter === 'all' ? undefined : statusFilter

  const historyQuery = useQuery({
    queryKey: ['jobs', 'history', { status: statusParam, search, page, perPage }],
    queryFn: () => fetchJobsHistory({ status: statusParam, search, page, perPage }),
    enabled: isAuthenticated,
    placeholderData: keepPreviousData,
    refetchInterval: 30000,
  })

  const meta = historyQuery.data?.meta
  const jobs = historyQuery.data?.jobs ?? []
  const showSkeleton = isAuthenticated && historyQuery.isLoading && !historyQuery.data
  const showEmpty = isAuthenticated && !historyQuery.isError && !historyQuery.isLoading && jobs.length === 0

  const handleStatusChange = (_event: MouseEvent<HTMLElement>, value: unknown) => {
    if (isStatusToggle(value)) {
      setStatusFilter(value)
      setPage(1)
    }
  }

  const handlePerPageChange = (value: string) => {
    const parsed = Number(value)
    if (Number.isFinite(parsed)) {
      setPerPage(parsed)
      setPage(1)
    }
  }

  const openJob = (jobId: string) => {
    navigate(`/jobs/${encodeURIComponent(jobId)}`)
  }

  return (
    <Container maxWidth="lg">
      <Box sx={{ mb: 3 }}>
        <Typography variant="h5" component="h1" gutterBottom sx={{ fontWeight: 800 }}>
          {labels.history.title}
        </Typography>

        {!isAuthenticated && (
          <Alert severity="info">
            {labels.history.loginToView}{' '}
            <Link component={RouterLink} to="/login">
              {labels.nav.login}
            </Link>
          </Alert>
        )}
      </Box>

      {isAuthenticated && (
        <Paper variant="outlined" sx={{ mb: 3, p: 2 }}>
          <Box sx={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: 2 }}>
            <ToggleButtonGroup
              exclusive
              size="small"
              value={statusFilter}
              onChange={handleStatusChange}
              aria-label={labels.history.status}
            >
              <ToggleButton value="all">{labels.history.statusAll}</ToggleButton>
              <ToggleButton value="success">{labels.history.statusSuccess}</ToggleButton>
              <ToggleButton value="fail">{labels.history.statusFail}</ToggleButton>
              <ToggleButton value="active">{labels.history.statusActive}</ToggleButton>
            </ToggleButtonGroup>

            <TextField
              size="small"
              label={labels.history.search}
              value={searchInput}
              onChange={(event) => setSearchInput(event.target.value)}
              sx={{ minWidth: 240, flex: '1 1 240px' }}
            />

            <TextField
              size="small"
              select
              label={labels.history.perPage}
              value={perPage}
              onChange={(event) => handlePerPageChange(event.target.value)}
              sx={{ minWidth: 110 }}
            >
              {PER_PAGE_OPTIONS.map((option) => (
                <MenuItem key={option} value={option}>
                  {option}
                </MenuItem>
              ))}
            </TextField>
          </Box>
        </Paper>
      )}

      {isAuthenticated && historyQuery.isError && (
        <Alert
          severity="error"
          sx={{ mb: 2 }}
          action={
            <Button color="inherit" size="small" onClick={() => void historyQuery.refetch()}>
              {labels.history.retry}
            </Button>
          }
        >
          {labels.history.loadError}
        </Alert>
      )}

      {isAuthenticated && (
        <Paper variant="outlined">
          <TableContainer
            sx={{ opacity: historyQuery.isPlaceholderData ? 0.6 : 1 }}
          >
            <Table size="small" aria-label={labels.history.title}>
              <TableHead>
                <TableRow>
                  <TableCell>{labels.history.colTitle}</TableCell>
                  <TableCell>{labels.history.colStatus}</TableCell>
                  <TableCell>{labels.history.colDisctype}</TableCell>
                  <TableCell>{labels.history.colDrive}</TableCell>
                  <TableCell>{labels.history.colStarted}</TableCell>
                  <TableCell>{labels.history.colCompleted}</TableCell>
                  <TableCell align="right">{labels.history.colDuration}</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {showSkeleton &&
                  Array.from({ length: SKELETON_ROWS }, (_, index) => (
                    <TableRow key={`skeleton-${index}`}>
                      <TableCell>
                        <Skeleton variant="text" width="70%" />
                      </TableCell>
                      <TableCell>
                        <Skeleton variant="rounded" width={64} height={22} />
                      </TableCell>
                      <TableCell>
                        <Skeleton variant="text" width={48} />
                      </TableCell>
                      <TableCell>
                        <Skeleton variant="text" width={80} />
                      </TableCell>
                      <TableCell>
                        <Skeleton variant="text" width={96} />
                      </TableCell>
                      <TableCell>
                        <Skeleton variant="text" width={96} />
                      </TableCell>
                      <TableCell align="right">
                        <Skeleton variant="text" width={56} sx={{ ml: 'auto' }} />
                      </TableCell>
                    </TableRow>
                  ))}
                {jobs.map((job) => {
                  const status = meaningfulText(job.status)
                  const disctype = meaningfulText(job.disctype)
                  const drive = meaningfulText(job.devpath)
                  const started = formatTimestamp(job.start_time)
                  const completed = formatTimestamp(job.stop_time)
                  const duration = formatDuration(job)
                  return (
                    <TableRow
                      key={job.job_id}
                      hover
                      tabIndex={0}
                      onClick={() => openJob(job.job_id)}
                      onKeyDown={(event) => {
                        if (event.key === 'Enter') {
                          openJob(job.job_id)
                        }
                      }}
                      sx={{ cursor: 'pointer' }}
                    >
                      <TableCell>
                        <Typography variant="body2" sx={{ wordBreak: 'break-word' }}>
                          {jobDisplayTitle(job)}
                        </Typography>
                      </TableCell>
                      <TableCell>
                        {status ? (
                          <Chip
                            label={status}
                            size="small"
                            color={statusChipColor(status)}
                            variant="outlined"
                          />
                        ) : (
                          '—'
                        )}
                      </TableCell>
                      <TableCell>{disctype ?? '—'}</TableCell>
                      <TableCell>{drive ?? '—'}</TableCell>
                      <TableCell title={meaningfulText(job.start_time) ?? undefined}>
                        {started ?? '—'}
                      </TableCell>
                      <TableCell title={meaningfulText(job.stop_time) ?? undefined}>
                        {completed ?? '—'}
                      </TableCell>
                      <TableCell align="right">{duration ?? '—'}</TableCell>
                    </TableRow>
                  )
                })}
              </TableBody>
            </Table>
          </TableContainer>

          {showEmpty && (
            <Box sx={{ py: 5, textAlign: 'center' }}>
              <Typography color="text.secondary">{labels.history.empty}</Typography>
            </Box>
          )}
        </Paper>
      )}

      {isAuthenticated && meta && meta.total > 0 && (
        <Box
          sx={{
            display: 'flex',
            flexWrap: 'wrap',
            alignItems: 'center',
            justifyContent: 'space-between',
            gap: 2,
            mt: 2,
          }}
        >
          <Typography variant="body2" color="text.secondary">
            {labels.history.total}: {meta.total}
          </Typography>
          <Pagination
            count={meta.pages}
            page={page}
            onChange={(_event, value) => setPage(value)}
            color="primary"
            showFirstButton
            showLastButton
          />
        </Box>
      )}
    </Container>
  )
}
