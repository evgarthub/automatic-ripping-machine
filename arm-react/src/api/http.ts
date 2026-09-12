const TOKEN_KEY = 'arm_spa_api_token'
const EXPIRY_KEY = 'arm_spa_api_expiry'
const CLOCK_SKEW_MS = 30_000

export interface StoredAuth {
  token: string
  expiry: string | null
}

type AuthListener = (auth: StoredAuth | null) => void

const authListeners = new Set<AuthListener>()

export function onAuthChange(listener: AuthListener): () => void {
  authListeners.add(listener)
  return () => {
    authListeners.delete(listener)
  }
}

function notifyAuthChange(auth: StoredAuth | null): void {
  for (const listener of authListeners) {
    listener(auth)
  }
}

export function getStoredToken(): string | null {
  try {
    return localStorage.getItem(TOKEN_KEY)
  } catch {
    return null
  }
}

export function getStoredExpiry(): string | null {
  try {
    return localStorage.getItem(EXPIRY_KEY)
  } catch {
    return null
  }
}

export function isStoredTokenExpired(): boolean {
  const expiry = getStoredExpiry()
  if (!expiry) {
    return false
  }
  const expiryMs = Date.parse(expiry)
  if (Number.isNaN(expiryMs)) {
    return true
  }
  return expiryMs - CLOCK_SKEW_MS <= Date.now()
}

export function setStoredAuth(auth: StoredAuth): void {
  try {
    localStorage.setItem(TOKEN_KEY, auth.token)
    if (auth.expiry) {
      localStorage.setItem(EXPIRY_KEY, auth.expiry)
    } else {
      localStorage.removeItem(EXPIRY_KEY)
    }
  } catch {
    /* ignore */
  }
  notifyAuthChange(auth)
}

export function clearStoredAuth(): void {
  try {
    localStorage.removeItem(TOKEN_KEY)
    localStorage.removeItem(EXPIRY_KEY)
  } catch {
    /* ignore */
  }
  notifyAuthChange(null)
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
  meta?: unknown
}

export interface ApiEnvelope<T> {
  data: T | undefined
  meta: Record<string, unknown> | undefined
}

function asRecord(value: unknown): Record<string, unknown> | undefined {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : undefined
}

interface AuthTokenData {
  token: string
  expiry: string
  user_id: number
}

async function requestRefreshedAuth(token: string): Promise<StoredAuth | null> {
  try {
    const res = await fetch(apiUrl('/api/v1/auth/refresh'), {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({}),
    })
    if (!res.ok) {
      return null
    }
    const json = (await res.json()) as Envelope<AuthTokenData>
    if (!json.success || !json.data?.token) {
      return null
    }
    return { token: json.data.token, expiry: json.data.expiry }
  } catch {
    return null
  }
}

let refreshPromise: Promise<StoredAuth | null> | null = null

function refreshAuth(): Promise<StoredAuth | null> {
  const token = getStoredToken()
  if (!token) {
    return Promise.resolve(null)
  }
  if (!refreshPromise) {
    refreshPromise = requestRefreshedAuth(token)
      .then((auth) => {
        if (auth) {
          setStoredAuth(auth)
          return auth
        }
        clearStoredAuth()
        window.location.replace(`${import.meta.env.BASE_URL.replace(/\/$/, '')}/login`)
        return null
      })
      .finally(() => {
        refreshPromise = null
      })
  }
  return refreshPromise
}

async function parseEnvelope<T>(res: Response): Promise<Envelope<T>> {
  let json: Envelope<T> | null = null
  try {
    json = (await res.json()) as Envelope<T>
  } catch {
    /* ignore */
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

  return json
}

async function performRequest(
  path: string,
  init: RequestInit & { auth?: boolean } = {},
): Promise<Response> {
  const { auth = true, headers: initHeaders, ...rest } = init
  const headers = new Headers(initHeaders)

  if (auth && !headers.has('Authorization')) {
    const token = getStoredToken()
    if (token) {
      headers.set('Authorization', `Bearer ${token}`)
    }
  }

  const url = apiUrl(path)
  let res = await fetch(url, { ...rest, headers })

  if (auth && res.status === 401) {
    const refreshed = await refreshAuth()
    if (refreshed) {
      headers.set('Authorization', `Bearer ${refreshed.token}`)
      res = await fetch(url, { ...rest, headers })
    }
  }

  return res
}

async function requestEnvelope<T>(
  path: string,
  init: RequestInit & { auth?: boolean } = {},
): Promise<Envelope<T>> {
  const res = await performRequest(path, init)
  return parseEnvelope<T>(res)
}

async function buildError(res: Response): Promise<ApiError> {
  const text = await res.text()
  let body: unknown
  try {
    body = JSON.parse(text) as unknown
  } catch {
    body = text
  }
  const error = asRecord(body)?.error
  const message =
    typeof error === 'string' && error.trim() !== ''
      ? error
      : res.statusText || `HTTP ${res.status}`
  return new ApiError(message, res.status, body)
}

export async function apiFetchJson<T>(
  path: string,
  init: RequestInit & { auth?: boolean } = {},
): Promise<T> {
  const envelope = await requestEnvelope<T>(path, init)
  return envelope.data as T
}

export async function apiFetchEnvelope<T>(
  path: string,
  init: RequestInit & { auth?: boolean } = {},
): Promise<ApiEnvelope<T>> {
  const envelope = await requestEnvelope<T>(path, init)
  return { data: envelope.data, meta: asRecord(envelope.meta) }
}

export async function apiFetchText(
  path: string,
  init: RequestInit & { auth?: boolean } = {},
): Promise<string> {
  const res = await performRequest(path, init)
  if (!res.ok) {
    throw await buildError(res)
  }
  return res.text()
}

export async function apiFetchBlob(
  path: string,
  init: RequestInit & { auth?: boolean } = {},
): Promise<Blob> {
  const res = await performRequest(path, init)
  if (!res.ok) {
    throw await buildError(res)
  }
  return res.blob()
}
