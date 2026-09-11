import { apiFetchJson, apiUrl } from './http'
import type { AuthTokenResponse } from './types'

export async function updatePassword(
  currentPassword: string,
  newPassword: string,
): Promise<void> {
  await apiFetchJson<unknown>('/api/v1/auth/password', {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      current_password: currentPassword,
      new_password: newPassword,
    }),
  })
}

export async function requestToken(
  username: string,
  password: string,
): Promise<AuthTokenResponse> {
  const url = apiUrl('/api/v1/auth/token')
  const res = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, password }),
  })

  const json = (await res.json()) as {
    success: boolean
    data?: AuthTokenResponse
    error?: string
  }

  if (!res.ok || !json.success || !json.data) {
    throw new Error(json.error || res.statusText || 'Auth failed')
  }

  return json.data
}

export function revokeToken(token: string): void {
  const url = apiUrl('/api/v1/auth/revoke')
  void fetch(url, {
    method: 'POST',
    headers: { Authorization: `Bearer ${token}` },
  }).catch(() => undefined)
}
