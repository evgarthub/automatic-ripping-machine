import { Alert, Box } from '@mui/material'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import {
  fetchNotificationTimeout,
  fetchNotifications,
  markNotificationRead,
} from '../api/notificationsApi'
import { labels } from '../labels'
import { useAuth } from '../auth/useAuth'
import {
  ToastContext,
  type ToastContextValue,
  type ToastItem,
  type ToastOptions,
} from './useToast'

export type { ToastOptions, ToastSeverity } from './useToast'

const MAX_VISIBLE_TOASTS = 3
const DEFAULT_TOAST_DURATION = 6500

interface ToastState {
  visible: ToastItem[]
  pending: ToastItem[]
}

function ToastEntry({ toast, onDismiss }: { toast: ToastItem; onDismiss: (id: string) => void }) {
  useEffect(() => {
    const timer = setTimeout(() => onDismiss(toast.id), toast.duration)
    return () => clearTimeout(timer)
  }, [onDismiss, toast.id, toast.duration])

  return (
    <Alert
      variant="filled"
      severity={toast.severity}
      onClose={() => onDismiss(toast.id)}
      closeText={labels.toast.dismiss}
      sx={{ boxShadow: 6 }}
    >
      {toast.message}
    </Alert>
  )
}

export function ToastProvider({ children }: { children: ReactNode }) {
  const { isAuthenticated } = useAuth()
  const queryClient = useQueryClient()
  const [state, setState] = useState<ToastState>({ visible: [], pending: [] })
  const shownIdsRef = useRef(new Set<string>())
  const stateRef = useRef(state)
  const pollErrorShownRef = useRef(false)

  useEffect(() => {
    stateRef.current = state
  }, [state])

  const timeoutQuery = useQuery({
    queryKey: ['notifications', 'timeout'],
    queryFn: fetchNotificationTimeout,
    enabled: isAuthenticated,
    staleTime: 5 * 60_000,
  })

  const pollQuery = useQuery({
    queryKey: ['notifications', 'toast'],
    queryFn: () => fetchNotifications({ page: 1, perPage: 50, unreadOnly: true }),
    enabled: isAuthenticated,
    refetchInterval: 10_000,
  })

  const defaultDuration = timeoutQuery.data ?? DEFAULT_TOAST_DURATION

  const notify = useCallback(
    (message: string, options?: ToastOptions) => {
      const notificationId = options?.notificationId
      setState((prev) => {
        if (
          notificationId !== undefined &&
          (prev.visible.some((toast) => toast.notificationId === notificationId) ||
            prev.pending.some((toast) => toast.notificationId === notificationId))
        ) {
          return prev
        }
        const toast: ToastItem = {
          id: notificationId !== undefined ? `db-${notificationId}` : crypto.randomUUID(),
          message,
          severity: options?.severity ?? 'info',
          duration: options?.duration ?? defaultDuration,
          notificationId,
        }
        if (prev.visible.length < MAX_VISIBLE_TOASTS) {
          return { visible: [...prev.visible, toast], pending: prev.pending }
        }
        return { visible: prev.visible, pending: [...prev.pending, toast] }
      })
    },
    [defaultDuration],
  )

  const dismiss = useCallback(
    (id: string) => {
      const notificationId = stateRef.current.visible.find((toast) => toast.id === id)
        ?.notificationId
      setState((prev) => {
        if (!prev.visible.some((toast) => toast.id === id)) {
          return prev
        }
        const [next, ...rest] = prev.pending
        return {
          visible: [...prev.visible.filter((toast) => toast.id !== id), ...(next ? [next] : [])],
          pending: rest,
        }
      })
      if (notificationId !== undefined) {
        markNotificationRead(notificationId)
          .catch(() => {})
          .finally(() => {
            void queryClient.invalidateQueries({ queryKey: ['notifications'] })
          })
      }
    },
    [queryClient],
  )

  useEffect(() => {
    const notifications = pollQuery.data?.notifications
    if (notifications === undefined) {
      return
    }
    for (const notification of notifications) {
      if (shownIdsRef.current.has(notification.id)) {
        continue
      }
      shownIdsRef.current.add(notification.id)
      const haystack = `${notification.title ?? ''} ${notification.message}`
      notify(
        notification.title && notification.title !== notification.message
          ? `${notification.title}: ${notification.message}`
          : notification.message,
        {
          notificationId: notification.id,
          severity: /fail|error/i.test(haystack) ? 'error' : 'info',
        },
      )
    }
  }, [notify, pollQuery.data])

  useEffect(() => {
    if (!pollQuery.isError) {
      pollErrorShownRef.current = false
      return
    }
    if (pollErrorShownRef.current) {
      return
    }
    pollErrorShownRef.current = true
    notify(labels.toast.pollError, { severity: 'error' })
  }, [notify, pollQuery.isError])

  const value = useMemo<ToastContextValue>(
    () => ({ notify, unreadCount: pollQuery.data?.meta?.total ?? 0 }),
    [notify, pollQuery.data],
  )

  return (
    <ToastContext.Provider value={value}>
      {children}
      <Box
        sx={{
          position: 'fixed',
          bottom: 24,
          right: 24,
          zIndex: 'snackbar',
          display: 'flex',
          flexDirection: 'column',
          gap: 1,
          maxWidth: { xs: 'calc(100vw - 32px)', sm: 420 },
        }}
      >
        {state.visible.map((toast) => (
          <ToastEntry key={toast.id} toast={toast} onDismiss={dismiss} />
        ))}
      </Box>
    </ToastContext.Provider>
  )
}
