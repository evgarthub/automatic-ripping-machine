import { apiFetchEnvelope, apiFetchJson } from './http'
import type {
  JobDetail,
  JobLogs,
  JobMetadataUpdate,
  JobProgress,
  JobSummary,
  PaginationMeta,
  TitleSearchApplyPayload,
  TitleSearchDetails,
  TitleSearchResponse,
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

export function searchJobTitles(
  jobId: string,
  title: string,
  year: string,
): Promise<TitleSearchResponse> {
  const qs = new URLSearchParams()
  qs.set('title', title)
  if (year.trim() !== '') {
    qs.set('year', year.trim())
  }
  return apiFetchJson<TitleSearchResponse>(
    `/api/v1/jobs/${encodeURIComponent(jobId)}/titlesearch?${qs.toString()}`,
  )
}

export function fetchTitleDetails(jobId: string, imdbId: string): Promise<TitleSearchDetails> {
  return apiFetchJson<TitleSearchDetails>(
    `/api/v1/jobs/${encodeURIComponent(jobId)}/titlesearch/details?imdb_id=${encodeURIComponent(imdbId)}`,
  )
}

export async function applyTitleSearch(
  jobId: string,
  payload: TitleSearchApplyPayload,
): Promise<JobDetail> {
  return apiFetchJson<JobDetail>(`/api/v1/jobs/${encodeURIComponent(jobId)}/titlesearch`, {
    method: 'POST',
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
