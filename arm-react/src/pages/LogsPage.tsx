import { useState } from 'react'
import type { MouseEvent } from 'react'
import DownloadIcon from '@mui/icons-material/Download'
import RefreshIcon from '@mui/icons-material/Refresh'
import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  CardHeader,
  Checkbox,
  Container,
  FormControlLabel,
  Grid,
  Link,
  MenuItem,
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
import { LogViewer } from '../components/LogViewer'
import { useQuery } from '@tanstack/react-query'
import { Link as RouterLink } from 'react-router-dom'
import { ApiError } from '../api/http'
import { downloadLog, fetchLogContent, fetchLogList } from '../api/logsApi'
import type { LogMode } from '../api/logsApi'
import { useAuth } from '../auth/useAuth'
import { labels } from '../labels'
import { humanizeRelativeTime } from '../utils/humanize'

const LIST_REFETCH_MS = 60000
const CONTENT_REFETCH_MS = 30000
const SKELETON_ROWS = 6

const TAIL_OPTIONS = [100, 500, 1000] as const

function isLogMode(value: unknown): value is LogMode {
  return value === 'armcat' || value === 'full'
}

function formatBytes(bytes: number): string {
  if (!Number.isFinite(bytes) || bytes <= 0) {
    return '—'
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

function isClientError(error: unknown): boolean {
  return error instanceof ApiError && (error.status === 400 || error.status === 404)
}

export function LogsPage() {
  const { isAuthenticated } = useAuth()
  const [selected, setSelected] = useState<string | null>(null)
  const [mode, setMode] = useState<LogMode>('full')
  const [lines, setLines] = useState<number | null>(500)
  const [autoRefresh, setAutoRefresh] = useState(true)
  const [downloadPending, setDownloadPending] = useState(false)
  const [downloadFailed, setDownloadFailed] = useState(false)

  const listQuery = useQuery({
    queryKey: ['logs'],
    queryFn: fetchLogList,
    enabled: isAuthenticated,
    refetchInterval: LIST_REFETCH_MS,
  })

  const contentQuery = useQuery({
    queryKey: ['logs', selected, mode, lines],
    queryFn: () =>
      fetchLogContent(selected ?? '', mode, lines === null ? undefined : lines),
    enabled: isAuthenticated && selected !== null,
    refetchInterval: autoRefresh ? CONTENT_REFETCH_MS : false,
    retry: (failureCount, error) => !isClientError(error) && failureCount < 2,
  })

  const logs = listQuery.data ?? []
  const content = contentQuery.data ?? ''

  const handleModeChange = (_event: MouseEvent<HTMLElement>, value: unknown) => {
    if (isLogMode(value)) {
      setMode(value)
    }
  }

  const handleLinesChange = (value: string) => {
    if (value === 'all') {
      setLines(null)
      return
    }
    const parsed = Number(value)
    if (Number.isFinite(parsed) && parsed > 0) {
      setLines(parsed)
    }
  }

  const handleDownload = async () => {
    if (selected === null || downloadPending) {
      return
    }
    setDownloadPending(true)
    setDownloadFailed(false)
    try {
      await downloadLog(selected)
    } catch {
      setDownloadFailed(true)
    } finally {
      setDownloadPending(false)
    }
  }

  const showSkeleton =
    isAuthenticated && listQuery.isLoading && !listQuery.data
  const showEmpty =
    isAuthenticated && !listQuery.isLoading && !listQuery.isError && logs.length === 0

  return (
    <Container maxWidth="lg">
      <Box sx={{ mb: 3 }}>
        <Typography variant="h5" component="h1" gutterBottom sx={{ fontWeight: 800 }}>
          {labels.logs.title}
        </Typography>

        {!isAuthenticated && (
          <Alert severity="info">
            {labels.logs.loginToView}{' '}
            <Link component={RouterLink} to="/login">
              {labels.nav.login}
            </Link>
          </Alert>
        )}
      </Box>

      {isAuthenticated && (
        <Grid container spacing={2} sx={{ alignItems: 'flex-start' }}>
          <Grid size={{ xs: 12, md: 5, lg: 4 }}>
            {listQuery.isError ? (
              <Alert
                severity="error"
                action={
                  <Button color="inherit" size="small" onClick={() => void listQuery.refetch()}>
                    {labels.logs.retry}
                  </Button>
                }
              >
                {labels.logs.loadError}
              </Alert>
            ) : (
              <Paper variant="outlined">
                <TableContainer sx={{ maxHeight: 560 }}>
                  <Table size="small" aria-label={labels.logs.title} stickyHeader>
                    <TableHead>
                      <TableRow>
                        <TableCell>{labels.logs.colName}</TableCell>
                        <TableCell align="right">{labels.logs.colSize}</TableCell>
                        <TableCell>{labels.logs.colModified}</TableCell>
                      </TableRow>
                    </TableHead>
                    <TableBody>
                      {showSkeleton &&
                        Array.from({ length: SKELETON_ROWS }, (_, index) => (
                          <TableRow key={`skeleton-${index}`}>
                            <TableCell>
                              <Skeleton variant="text" width="80%" />
                            </TableCell>
                            <TableCell align="right">
                              <Skeleton variant="text" width={48} sx={{ ml: 'auto' }} />
                            </TableCell>
                            <TableCell>
                              <Skeleton variant="text" width={72} />
                            </TableCell>
                          </TableRow>
                        ))}
                      {logs.map((log) => (
                        <TableRow
                          key={log.name}
                          hover
                          selected={log.name === selected}
                          tabIndex={0}
                          onClick={() => setSelected(log.name)}
                          onKeyDown={(event) => {
                            if (event.key === 'Enter') {
                              setSelected(log.name)
                            }
                          }}
                          sx={{ cursor: 'pointer' }}
                        >
                          <TableCell sx={{ wordBreak: 'break-word' }}>
                            <Typography variant="body2">{log.name}</Typography>
                          </TableCell>
                          <TableCell align="right">{formatBytes(log.size_bytes)}</TableCell>
                          <TableCell title={log.modified}>
                            {humanizeRelativeTime(log.modified)}
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </TableContainer>

                {showEmpty && (
                  <Box sx={{ py: 5, textAlign: 'center' }}>
                    <Typography color="text.secondary">{labels.logs.empty}</Typography>
                  </Box>
                )}
              </Paper>
            )}
          </Grid>

          <Grid size={{ xs: 12, md: 7, lg: 8 }}>
            <Card variant="outlined">
              <CardHeader
                title={selected ?? labels.logs.viewerTitle}
                titleTypographyProps={{ sx: { wordBreak: 'break-word' } }}
              />
              <CardContent>
                <Box
                  sx={{
                    display: 'flex',
                    flexWrap: 'wrap',
                    alignItems: 'center',
                    gap: 2,
                    mb: 2,
                  }}
                >
                  <ToggleButtonGroup
                    exclusive
                    size="small"
                    value={mode}
                    onChange={handleModeChange}
                    aria-label={labels.logs.modeLabel}
                  >
                    <ToggleButton value="armcat">{labels.logs.modeArmcat}</ToggleButton>
                    <ToggleButton value="full">{labels.logs.modeFull}</ToggleButton>
                  </ToggleButtonGroup>

                  <TextField
                    size="small"
                    select
                    label={labels.logs.linesLabel}
                    value={lines === null ? 'all' : String(lines)}
                    onChange={(event) => handleLinesChange(event.target.value)}
                    sx={{ minWidth: 110 }}
                  >
                    {TAIL_OPTIONS.map((option) => (
                      <MenuItem key={option} value={String(option)}>
                        {option}
                      </MenuItem>
                    ))}
                    <MenuItem value="all">{labels.logs.linesAll}</MenuItem>
                  </TextField>

                  <Button
                    size="small"
                    startIcon={<RefreshIcon />}
                    disabled={selected === null}
                    onClick={() => {
                      void contentQuery.refetch()
                      void listQuery.refetch()
                    }}
                  >
                    {labels.logs.refresh}
                  </Button>

                  <Button
                    size="small"
                    variant="outlined"
                    startIcon={<DownloadIcon />}
                    disabled={selected === null || downloadPending}
                    onClick={() => void handleDownload()}
                  >
                    {labels.logs.download}
                  </Button>

                  <FormControlLabel
                    control={
                      <Checkbox
                        size="small"
                        checked={autoRefresh}
                        onChange={(event) => setAutoRefresh(event.target.checked)}
                      />
                    }
                    label={labels.logs.autoRefresh}
                  />
                </Box>

                {downloadFailed && (
                  <Alert severity="error" sx={{ mb: 2 }}>
                    {labels.logs.downloadError}
                  </Alert>
                )}

                {selected === null ? (
                  <Box sx={{ py: 10, textAlign: 'center' }}>
                    <Typography color="text.secondary">{labels.logs.selectPrompt}</Typography>
                  </Box>
                ) : contentQuery.isError ? (
                  <Alert severity={isNotFound(contentQuery.error) ? 'info' : 'error'}>
                    {isNotFound(contentQuery.error)
                      ? labels.logs.contentMissing
                      : extractErrorMessage(contentQuery.error) ?? labels.logs.contentLoadError}
                  </Alert>
                ) : contentQuery.isPending ? (
                  <Skeleton variant="rounded" height={360} />
                ) : (
                  <LogViewer
                    content={content}
                    isLoading={contentQuery.isPending}
                    onRefresh={() => {
                      void contentQuery.refetch()
                      void listQuery.refetch()
                    }}
                  />
                )}
              </CardContent>
            </Card>
          </Grid>
        </Grid>
      )}
    </Container>
  )
}
