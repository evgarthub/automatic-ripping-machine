const TOKEN_KEY = 'arm_spa_api_token'

export function getStoredToken(): string | null {
  try {
    return localStorage.getItem(TOKEN_KEY)
  } catch {
    return null
  }
}

export function setStoredToken(token: string | null): void {
  try {
    if (token) {
      localStorage.setItem(TOKEN_KEY, token)
    } else {
      localStorage.removeItem(TOKEN_KEY)
    }
  } catch {
    /* ignore */
  }
}

const rawBase = import.meta.env.VITE_ARM_API_BASE ?? ''
const API_BASE = rawBase.replace(/\/$/, '')

export function apiUrl(path: string): string {
  const p = path.startsWith('/') ? path : `/${path}`
  if (!API_BASE) {
    return p
  }
  return `${API_BASE}${p}`
}

export class ApiError extends Error {
  status: number
  body?: unknown

  constructor(message: string, status: number, body?: unknown) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.body = body
  }
}

interface Envelope<T> {
  success: boolean
  data?: T
  error?: string
}

export async function apiFetchJson<T>(
  path: string,
  init: RequestInit & { auth?: boolean } = {},
): Promise<T> {
  const { auth = true, headers: initHeaders, ...rest } = init
  const headers = new Headers(initHeaders)

  if (auth && !headers.has('Authorization')) {
    const token = getStoredToken()
    if (token) {
      headers.set('Authorization', `Bearer ${token}`)
    }
  }

  const url = apiUrl(path)
  const res = await fetch(url, { ...rest, headers })

  let json: Envelope<T> | null = null
  try {
    json = (await res.json()) as Envelope<T>
  } catch {
    json = null
  }

  if (!res.ok) {
    const msg =
      (json && 'error' in json && json.error) ||
      res.statusText ||
      `HTTP ${res.status}`
    throw new ApiError(String(msg), res.status, json)
  }

  if (!json || typeof json.success !== 'boolean') {
    throw new ApiError('Invalid API response', res.status, json)
  }

  if (!json.success) {
    throw new ApiError(json.error || 'Request failed', res.status, json)
  }

  return json.data as T
}
