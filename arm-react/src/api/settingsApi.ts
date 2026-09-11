import { apiFetchJson } from './http'

export type ArmSettingValue = boolean | number | string
export type ArmSettingsValues = Record<string, ArmSettingValue>

export interface ArmSettingsData {
  values: ArmSettingsValues
  comments: Record<string, string>
  read_only: boolean
}

export interface UiSettings {
  id: string
  index_refresh: string
  use_icons: string
  save_remote_images: string
  bootstrap_skin: string
  language: string
  database_limit: string
  notify_refresh: string
}

export interface UiSettingsUpdate {
  index_refresh?: number
  use_icons?: boolean
  save_remote_images?: boolean
  bootstrap_skin?: string
  language?: string
  database_limit?: number
  notify_refresh?: number
}

export interface FileSettingsData {
  content: string
  read_only: boolean
}

export interface FileContentUpdateResult {
  content: string
}

export interface AppriseTestResult {
  message: string
}

export function fetchArmSettings(): Promise<ArmSettingsData> {
  return apiFetchJson<ArmSettingsData>('/api/v1/settings')
}

export function updateArmSettings(changes: Record<string, ArmSettingValue>): Promise<ArmSettingsData> {
  return apiFetchJson<ArmSettingsData>('/api/v1/settings', {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(changes),
  })
}

export function fetchUiSettings(): Promise<UiSettings> {
  return apiFetchJson<UiSettings>('/api/v1/settings/ui')
}

export function updateUiSettings(changes: UiSettingsUpdate): Promise<UiSettings> {
  return apiFetchJson<UiSettings>('/api/v1/settings/ui', {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(changes),
  })
}

export function fetchAbcdeSettings(): Promise<FileSettingsData> {
  return apiFetchJson<FileSettingsData>('/api/v1/settings/abcde')
}

export function updateAbcdeSettings(content: string): Promise<FileContentUpdateResult> {
  return apiFetchJson<FileContentUpdateResult>('/api/v1/settings/abcde', {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ content }),
  })
}

export function fetchAppriseSettings(): Promise<FileSettingsData> {
  return apiFetchJson<FileSettingsData>('/api/v1/settings/apprise')
}

export function updateAppriseSettings(content: string): Promise<FileContentUpdateResult> {
  return apiFetchJson<FileContentUpdateResult>('/api/v1/settings/apprise', {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ content }),
  })
}

export function testAppriseNotification(): Promise<AppriseTestResult> {
  return apiFetchJson<AppriseTestResult>('/api/v1/settings/apprise/test', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({}),
  })
}
