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
