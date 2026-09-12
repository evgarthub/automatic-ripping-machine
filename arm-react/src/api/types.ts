export interface SystemDashboard {
  arm_name: string
  server: {
    name: string
    description: string
    cpu: string
    mem_total_gb: number
  }
  cpu_percent: number
  cpu_temp_c: number
  memory: {
    total_gb: number
    free_gb: number
    used_gb: number
    percent: number
  }
  storage: {
    transcode: { path: string; free_gb: number; percent_used: number }
    completed: { path: string; free_gb: number; percent_used: number }
  }
  hw_support: {
    intel: boolean
    nvidia: boolean
    amd: boolean
  }
}

export interface AuthTokenResponse {
  token: string
  expiry: string
  user_id: number
}

export interface PaginationMeta {
  total: number
  page: number
  per_page: number
  pages: number
}

export interface JobSummary {
  job_id: string
  arm_version: string
  crc_id: string
  logfile: string
  start_time: string
  stop_time: string
  job_length: string
  status: string
  no_of_titles: string
  title: string
  title_auto: string
  title_manual: string
  year: string
  video_type: string
  imdb_id: string
  poster_url: string
  devpath: string
  mountpoint: string
  hasnicetitle: string
  errors: string
  disctype: string
  label: string
  path: string
  ejected: string
  updated: string
  stage?: string | null
  progress?: string | number | null
  progress_round?: string | number | null
  eta?: string | null
}

export interface JobDetail {
  job_id: string
  arm_version: string
  crc_id: string
  logfile: string
  start_time: string
  stop_time: string
  job_length: string
  status: string
  stage: string
  no_of_titles: string
  title: string
  title_auto: string
  title_manual: string
  year: string
  year_auto: string
  year_manual: string
  video_type: string
  video_type_auto: string
  video_type_manual: string
  imdb_id: string
  imdb_id_auto: string
  imdb_id_manual: string
  poster_url: string
  poster_url_auto: string
  poster_url_manual: string
  devpath: string
  mountpoint: string
  hasnicetitle: string
  errors: string
  disctype: string
  label: string
  path: string
  ejected: string
  updated: string
  pid: string
  pid_hash: string
  is_iso: string
  manual_start: string
  manual_mode: string
  has_track_99?: string
  progress?: string | number | null
  progress_round?: string | number | null
  eta?: string | null
  config?: Record<string, string> | null
  tracks?: TrackInfo[]
}

export interface TrackInfo {
  track_id: string
  job_id: string
  track_number: string
  length: string
  aspect_ratio: string
  fps: string
  main_feature: string
  basename: string
  filename: string
  orig_filename: string
  new_filename: string
  ripped: string
  status: string
  error: string
  source: string
  process: string
  chapters: string
  filesize: string
}

export interface JobLogs {
  job_id: number
  logfile: string
  content: string
}

export interface JobMetadataUpdate {
  title?: string
  year?: string
  video_type?: string
  imdb_id?: string
  poster_url?: string
}

export interface TitleSearchResult {
  imdb_id: string
  title: string
  year: string
  poster: string
  type: string
}

export interface TitleSearchResponse {
  results: TitleSearchResult[]
  retried_without_year: boolean
}

export interface TitleSearchDetails extends TitleSearchResult {
  plot: string | null
  background_url: string | null
}

export interface TitleSearchApplyPayload {
  imdb_id?: string
  title?: string
  year?: string
}

export interface JobProgress {
  job_id: number
  status: string | null
  stage: string | null
  progress: string | number | null
  eta: string | null
}

export type DriveMode = 'auto' | 'manual'

export interface DriveJobInfo {
  job_id: number
  status: string | null
  video_type: string | null
  title: string | null
  year: string | null
}

export interface SystemDrive {
  drive_id: number
  name: string | null
  description: string | null
  type: string | null
  mount: string | null
  maker: string | null
  model: string | null
  serial: string | null
  connection: string | null
  firmware: string | null
  location: string | null
  stale: boolean | null
  mdisc: number | null
  drive_mode: string | null
  read_cd: boolean | null
  read_dvd: boolean | null
  read_bd: boolean | null
  processing: boolean
  job_current: DriveJobInfo | null
  job_previous: DriveJobInfo | null
}

export interface NotificationItem {
  id: string
  seen: string
  trigger_time: string
  dismiss_time: string | null
  title: string | null
  message: string
  cleared: string
  cleared_time: string | null
}
