import { apiFetchJson } from './http'
import type { DriveMode, SystemDashboard, SystemDrive } from './types'

export function fetchSystemDashboard() {
  return apiFetchJson<SystemDashboard>('/api/v1/system/dashboard')
}

export function fetchSystemDrivesAdmin(): Promise<SystemDrive[]> {
  return apiFetchJson<SystemDrive[]>('/api/v1/system/drives')
}

export interface DriveScanResult {
  new_drives: number
}

export interface SystemDriveUpdate {
  name?: string
  description?: string
  drive_mode?: DriveMode
}

export function scanSystemDrives(): Promise<DriveScanResult> {
  return apiFetchJson<DriveScanResult>('/api/v1/system/drives/scan', {
    method: 'POST',
  })
}

export function updateSystemDrive(
  driveId: number,
  changes: SystemDriveUpdate,
): Promise<SystemDrive> {
  return apiFetchJson<SystemDrive>(`/api/v1/system/drives/${driveId}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(changes),
  })
}

export async function removeSystemDrive(driveId: number): Promise<void> {
  await apiFetchJson<unknown>(`/api/v1/system/drives/${driveId}`, {
    method: 'DELETE',
  })
}

export async function manualStartSystemDrive(driveId: number): Promise<void> {
  await apiFetchJson<unknown>(`/api/v1/system/drives/${driveId}/manual`, {
    method: 'POST',
  })
}

export async function ejectSystemDrive(driveName: string): Promise<void> {
  await apiFetchJson<unknown>(
    `/api/v1/system/drives/${encodeURIComponent(driveName)}/eject`,
    {
      method: 'POST',
    },
  )
}
