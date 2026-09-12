import { apiFetchEnvelope, apiFetchJson } from './http'
import type {
  JobDetail,
  JobLogs,
  JobMetadataUpdate,
  JobProgress,
  JobSummary,
  PaginationMeta,
} from './types'

export function fetchActiveJobs(): Promise<JobSummary[]> {
  return apiFetchJson<JobSummary[]>('/api/v1/jobs?status=active&page=1&per_page=50')
}

export function fetchJobDetail(jobId: string): Promise<JobDetail> {
  return apiFetchJson<JobDetail>(`/api/v1/jobs/${encodeURIComponent(jobId)}`)
}

export function fetchJobLogs(jobId: string): Promise<JobLogs> {
  return apiFetchJson<JobLogs>(`/api/v1/jobs/${encodeURIComponent(jobId)}/logs`)
}

export async function abandonJob(jobId: string): Promise<void> {
  await apiFetchEnvelope<null>(`/api/v1/jobs/${encodeURIComponent(jobId)}/actions`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ action: 'abandon' }),
  })
}

export async function updateJobMetadata(
  jobId: string,
  payload: JobMetadataUpdate,
): Promise<JobDetail> {
  return apiFetchJson<JobDetail>(`/api/v1/jobs/${encodeURIComponent(jobId)}/metadata`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
}

export async function deleteJob(jobId: string): Promise<void> {
  await apiFetchEnvelope<null>(`/api/v1/jobs/${encodeURIComponent(jobId)}`, {
    method: 'DELETE',
  })
}

export function fetchJobProgress(jobId: string): Promise<JobProgress> {
  return apiFetchJson<JobProgress>(`/api/v1/jobs/${encodeURIComponent(jobId)}/progress`)
}

export type JobStatusFilter = 'active' | 'success' | 'fail'

export interface JobsHistoryParams {
  status?: JobStatusFilter
  search?: string
  page?: number
  perPage?: number
}

export interface JobsHistoryPage {
  jobs: JobSummary[]
  meta: PaginationMeta
}

function toNumber(value: unknown, fallback: number): number {
  const parsed = typeof value === 'number' ? value : Number(value)
  return Number.isFinite(parsed) ? parsed : fallback
}

export async function fetchJobsHistory(params: JobsHistoryParams): Promise<JobsHistoryPage> {
  const qs = new URLSearchParams()
  if (params.status) {
    qs.set('status', params.status)
  }
  if (params.search) {
    qs.set('search', params.search)
  }
  qs.set('page', String(Math.max(1, params.page ?? 1)))
  qs.set('per_page', String(params.perPage ?? 50))

  const { data, meta } = await apiFetchEnvelope<JobSummary[]>(`/api/v1/jobs?${qs.toString()}`)

  return {
    jobs: data ?? [],
    meta: {
      total: toNumber(meta?.total, 0),
      page: toNumber(meta?.page, 1),
      per_page: toNumber(meta?.per_page, 50),
      pages: toNumber(meta?.pages, 1),
    },
  }
}
