import { apiFetchEnvelope, apiFetchJson } from './http'
import type { NotificationItem, PaginationMeta } from './types'

export interface NotificationsListParams {
  page?: number
  perPage?: number
  unreadOnly?: boolean
}

export interface NotificationsListPage {
  notifications: NotificationItem[]
  meta: PaginationMeta
}

export interface ClearNotificationsResult {
  cleared: number
}

function toNumber(value: unknown, fallback: number): number {
  const parsed = typeof value === 'number' ? value : Number(value)
  return Number.isFinite(parsed) ? parsed : fallback
}

export async function fetchNotifications(
  params: NotificationsListParams,
): Promise<NotificationsListPage> {
  const qs = new URLSearchParams()
  qs.set('page', String(Math.max(1, params.page ?? 1)))
  qs.set('per_page', String(params.perPage ?? 50))
  if (params.unreadOnly) {
    qs.set('unread_only', 'true')
  }

  const { data, meta } = await apiFetchEnvelope<NotificationItem[]>(
    `/api/v1/notifications?${qs.toString()}`,
  )

  return {
    notifications: data ?? [],
    meta: {
      total: toNumber(meta?.total, 0),
      page: toNumber(meta?.page, 1),
      per_page: toNumber(meta?.per_page, 50),
      pages: toNumber(meta?.pages, 1),
    },
  }
}

export async function markNotificationRead(notificationId: string): Promise<void> {
  await apiFetchEnvelope<null>(
    `/api/v1/notifications/${encodeURIComponent(notificationId)}/read`,
    { method: 'PUT' },
  )
}

export async function clearNotifications(
  notificationId?: string,
): Promise<ClearNotificationsResult> {
  const path =
    notificationId !== undefined
      ? `/api/v1/notifications?id=${encodeURIComponent(notificationId)}`
      : '/api/v1/notifications'
  const data = await apiFetchJson<{ cleared: number }>(path, { method: 'DELETE' })
  return { cleared: toNumber(data?.cleared, 0) }
}

export async function fetchNotificationTimeout(): Promise<number> {
  const data = await apiFetchJson<{ timeout: number }>('/api/v1/notifications/settings/timeout')
  return toNumber(data?.timeout, 6500)
}
