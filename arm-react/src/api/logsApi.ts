import { apiFetchBlob, apiFetchJson, apiFetchText } from './http'

export interface LogFileInfo {
  name: string
  size_bytes: number
  modified: string
}

export type LogMode = 'armcat' | 'full'

export function fetchLogList(): Promise<LogFileInfo[]> {
  return apiFetchJson<LogFileInfo[]>('/api/v1/logs')
}

export function fetchLogContent(
  name: string,
  mode: LogMode,
  lines?: number,
): Promise<string> {
  const qs = new URLSearchParams({ mode })
  if (lines !== undefined) {
    qs.set('lines', String(lines))
  }
  return apiFetchText(`/api/v1/logs/${encodeURIComponent(name)}?${qs.toString()}`)
}

export async function downloadLog(name: string): Promise<void> {
  const blob = await apiFetchBlob(
    `/api/v1/logs/${encodeURIComponent(name)}?mode=download`,
  )
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = name
  document.body.appendChild(anchor)
  anchor.click()
  anchor.remove()
  URL.revokeObjectURL(url)
}
