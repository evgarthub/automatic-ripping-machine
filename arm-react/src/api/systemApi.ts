import { apiFetchJson } from './http'
import type { SystemDashboard } from './types'

export function fetchSystemDashboard() {
  return apiFetchJson<SystemDashboard>('/api/v1/system/dashboard')
}
