import { useState } from 'react'
import type { MouseEvent } from 'react'
import {
  Alert,
  Box,
  Button,
  Chip,
  Container,
  Dialog,
  DialogActions,
  DialogContent,
  DialogContentText,
  DialogTitle,
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
import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link as RouterLink } from 'react-router-dom'
import {
  clearNotifications,
  fetchNotifications,
  markNotificationRead,
} from '../api/notificationsApi'
import { useAuth } from '../auth/useAuth'
import { labels } from '../labels'
import { useToast } from '../providers/useToast'
import { humanizeRelativeTime } from '../utils/humanize'

type FilterToggle = 'all' | 'unread'

const PER_PAGE_OPTIONS = [25, 50, 100] as const
const SKELETON_ROWS = 8

function isFilterToggle(value: unknown): value is FilterToggle {
  return value === 'all' || value === 'unread'
}

function flagValue(value: string | null | undefined): boolean {
  return value?.trim().toLowerCase() === 'true'
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

export function NotificationsPage() {
  const { isAuthenticated } = useAuth()
  const queryClient = useQueryClient()
  const { notify } = useToast()

  const [filter, setFilter] = useState<FilterToggle>('all')
  const [page, setPage] = useState(1)
  const [perPage, setPerPage] = useState<number>(25)
  const [clearOpen, setClearOpen] = useState(false)

  const unreadOnly = filter === 'unread'

  const notificationsQuery = useQuery({
    queryKey: ['notifications', { page, perPage, unreadOnly }],
    queryFn: () => fetchNotifications({ page, perPage, unreadOnly }),
    enabled: isAuthenticated,
    placeholderData: keepPreviousData,
    refetchInterval: 30000,
  })

  const markReadMutation = useMutation({
    mutationFn: (notificationId: string) => markNotificationRead(notificationId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['notifications'] })
    },
    onError: () => {
      notify(labels.notifications.markReadError, { severity: 'error' })
    },
  })

  const clearMutation = useMutation({
    mutationFn: () => clearNotifications(),
    onSuccess: (result) => {
      setClearOpen(false)
      void queryClient.invalidateQueries({ queryKey: ['notifications'] })
      if (result.cleared > 0) {
        notify(labels.notifications.cleared, { severity: 'success' })
      } else {
        notify(labels.notifications.clearNothing, { severity: 'info' })
      }
    },
    onError: () => {
      notify(labels.notifications.clearError, { severity: 'error' })
    },
  })

  const meta = notificationsQuery.data?.meta
  const notifications = notificationsQuery.data?.notifications ?? []
  const showSkeleton =
    isAuthenticated && notificationsQuery.isLoading && !notificationsQuery.data
  const showEmpty =
    isAuthenticated &&
    !notificationsQuery.isError &&
    !notificationsQuery.isLoading &&
    notifications.length === 0

  const handleFilterChange = (_event: MouseEvent<HTMLElement>, value: unknown) => {
    if (isFilterToggle(value)) {
      setFilter(value)
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

  return (
    <Container maxWidth="lg">
      <Box sx={{ mb: 3 }}>
        <Typography variant="h5" component="h1" gutterBottom sx={{ fontWeight: 800 }}>
          {labels.notifications.title}
        </Typography>

        {!isAuthenticated && (
          <Alert severity="info">
            {labels.notifications.loginToView}{' '}
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
              value={filter}
              onChange={handleFilterChange}
              aria-label={labels.notifications.filter}
            >
              <ToggleButton value="all">{labels.notifications.filterAll}</ToggleButton>
              <ToggleButton value="unread">{labels.notifications.filterUnread}</ToggleButton>
            </ToggleButtonGroup>

            <Box sx={{ flex: '1 1 auto' }} />

            <Button
              variant="outlined"
              color="error"
              onClick={() => setClearOpen(true)}
              disabled={clearMutation.isPending}
            >
              {labels.notifications.clearAll}
            </Button>

            <TextField
              size="small"
              select
              label={labels.notifications.perPage}
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

      {isAuthenticated && notificationsQuery.isError && (
        <Alert
          severity="error"
          sx={{ mb: 2 }}
          action={
            <Button
              color="inherit"
              size="small"
              onClick={() => void notificationsQuery.refetch()}
            >
              {labels.notifications.retry}
            </Button>
          }
        >
          {labels.notifications.loadError}
        </Alert>
      )}

      {isAuthenticated && (
        <Paper variant="outlined">
          <TableContainer
            sx={{ opacity: notificationsQuery.isPlaceholderData ? 0.6 : 1 }}
          >
            <Table size="small" aria-label={labels.notifications.title}>
              <TableHead>
                <TableRow>
                  <TableCell>{labels.notifications.colMessage}</TableCell>
                  <TableCell>{labels.notifications.colReceived}</TableCell>
                  <TableCell>{labels.notifications.colStatus}</TableCell>
                  <TableCell align="right">{labels.notifications.colActions}</TableCell>
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
                        <Skeleton variant="text" width={96} />
                      </TableCell>
                      <TableCell>
                        <Skeleton variant="rounded" width={64} height={22} />
                      </TableCell>
                      <TableCell align="right">
                        <Skeleton variant="text" width={72} sx={{ ml: 'auto' }} />
                      </TableCell>
                    </TableRow>
                  ))}
                {notifications.map((notification) => {
                  const seen = flagValue(notification.seen)
                  const cleared = flagValue(notification.cleared)
                  const title = meaningfulText(notification.title)
                  const message = meaningfulText(notification.message)
                  const received = formatTimestamp(notification.trigger_time)
                  const canMarkRead = !seen && !cleared
                  return (
                    <TableRow
                      key={notification.id}
                      hover
                      sx={cleared ? { opacity: 0.55 } : undefined}
                    >
                      <TableCell>
                        {title && (
                          <Typography variant="body2" sx={{ wordBreak: 'break-word' }}>
                            {title}
                          </Typography>
                        )}
                        <Typography
                          variant="body2"
                          color={cleared ? 'text.secondary' : 'text.primary'}
                          sx={{
                            wordBreak: 'break-word',
                            fontWeight: seen || cleared ? 400 : 700,
                          }}
                        >
                          {message ?? '—'}
                        </Typography>
                      </TableCell>
                      <TableCell title={meaningfulText(notification.trigger_time) ?? undefined}>
                        {received ?? '—'}
                      </TableCell>
                      <TableCell>
                        {cleared ? (
                          <Chip
                            label={labels.notifications.statusCleared}
                            size="small"
                            variant="outlined"
                            color="default"
                          />
                        ) : seen ? (
                          <Chip
                            label={labels.notifications.statusRead}
                            size="small"
                            variant="outlined"
                            color="default"
                          />
                        ) : (
                          <Chip
                            label={labels.notifications.statusUnread}
                            size="small"
                            color="primary"
                          />
                        )}
                      </TableCell>
                      <TableCell align="right">
                        {canMarkRead && (
                          <Button
                            size="small"
                            onClick={() => markReadMutation.mutate(notification.id)}
                            disabled={
                              markReadMutation.isPending &&
                              markReadMutation.variables === notification.id
                            }
                          >
                            {labels.notifications.markRead}
                          </Button>
                        )}
                      </TableCell>
                    </TableRow>
                  )
                })}
              </TableBody>
            </Table>
          </TableContainer>

          {showEmpty && (
            <Box sx={{ py: 5, textAlign: 'center' }}>
              <Typography color="text.secondary">
                {unreadOnly ? labels.notifications.emptyUnread : labels.notifications.empty}
              </Typography>
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
            {labels.notifications.total}: {meta.total}
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

      <ClearAllDialog
        open={clearOpen}
        pending={clearMutation.isPending}
        onConfirm={() => clearMutation.mutate()}
        onClose={() => setClearOpen(false)}
      />
    </Container>
  )
}

function ClearAllDialog({
  open,
  pending,
  onConfirm,
  onClose,
}: {
  open: boolean
  pending: boolean
  onConfirm: () => void
  onClose: () => void
}) {
  return (
    <Dialog open={open} onClose={pending ? undefined : onClose} maxWidth="xs" fullWidth>
      <DialogTitle>{labels.notifications.clearAllTitle}</DialogTitle>
      <DialogContent>
        <DialogContentText>{labels.notifications.clearAllMessage}</DialogContentText>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose} disabled={pending}>
          {labels.notifications.cancel}
        </Button>
        <Button variant="contained" color="error" onClick={onConfirm} disabled={pending}>
          {labels.notifications.clearAllConfirm}
        </Button>
      </DialogActions>
    </Dialog>
  )
}
