import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { apiClient } from "@/lib/api"

interface SystemHealth {
  status: string
  uptime_seconds: number
  uptime_human: string
  db_size_mb: number
  chroma_chunks: number
  memory_mb: number
  total_requests_tracked: number
  total_errors: number
  scheduler: JobStatus[] | null
}

interface TokenSummary {
  today: {
    input_tokens: number
    output_tokens: number
    total_tokens: number
    cost_usd: number
  }
  trend_7d: {
    date: string
    input_tokens: number
    output_tokens: number
    total_tokens: number
    cost_usd: number
  }[]
  by_endpoint: { endpoint: string; tokens: number }[]
}

interface EndpointStat {
  path: string
  request_count: number
  error_count: number
  error_rate: number
  p50_ms: number
  p95_ms: number
  p99_ms: number
}

interface ErrorEntry {
  key: string
  count: number
}

interface JobStatus {
  job_id: string
  name: string
  next_run: string | null
  state: string
  last_run?: {
    job_name: string
    started_at: string
    finished_at: string | null
    status: string
    records_processed: number
    error_message: string | null
  } | null
}

interface HistoryEntry {
  id: number
  job_name: string
  started_at: string
  finished_at: string | null
  status: string
  records_processed: number
  error_message: string | null
}

interface ApiResponse<T> {
  data: T
  meta?: Record<string, unknown>
}

// Monitoring hooks
export function useSystemHealth() {
  return useQuery({
    queryKey: ["monitoring", "health"],
    queryFn: () => apiClient<ApiResponse<SystemHealth>>("/api/monitoring/health"),
    refetchInterval: 30_000,
  })
}

export function useTokenUsage() {
  return useQuery({
    queryKey: ["monitoring", "tokens"],
    queryFn: () => apiClient<ApiResponse<TokenSummary>>("/api/monitoring/tokens"),
    refetchInterval: 30_000,
  })
}

export function useEndpointStats() {
  return useQuery({
    queryKey: ["monitoring", "endpoints"],
    queryFn: () => apiClient<ApiResponse<EndpointStat[]>>("/api/monitoring/endpoints"),
    refetchInterval: 30_000,
  })
}

export function useRecentErrors() {
  return useQuery({
    queryKey: ["monitoring", "errors"],
    queryFn: () => apiClient<ApiResponse<ErrorEntry[]>>("/api/monitoring/errors"),
    refetchInterval: 30_000,
  })
}

// Scheduler hooks
export function useSchedulerStatus() {
  return useQuery({
    queryKey: ["scheduler", "status"],
    queryFn: () => apiClient<ApiResponse<JobStatus[]>>("/api/scheduler/status"),
    refetchInterval: 30_000,
  })
}

export function useSchedulerHistory(jobName?: string, limit = 20) {
  return useQuery({
    queryKey: ["scheduler", "history", jobName, limit],
    queryFn: () =>
      apiClient<ApiResponse<HistoryEntry[]>>("/api/scheduler/history", {
        params: { job_name: jobName || undefined, limit },
      }),
  })
}

export function useTriggerJob() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (jobId: string) =>
      apiClient<ApiResponse<{ job_id: string; triggered: boolean }>>(
        `/api/scheduler/trigger/${jobId}`,
        { method: "POST" }
      ),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["scheduler"] })
    },
  })
}

// Data freshness hook (for sidebar widget)
export function useDataFreshness() {
  return useQuery({
    queryKey: ["scheduler", "status"],
    queryFn: () => apiClient<ApiResponse<JobStatus[]>>("/api/scheduler/status"),
    refetchInterval: 60_000, // Check every minute
    select: (data) => {
      const jobs = data.data || []
      // Find the most recent successful ETL job
      let latestSuccess: string | null = null
      for (const job of jobs) {
        if (job.last_run?.status === "success" && job.last_run.finished_at) {
          if (!latestSuccess || job.last_run.finished_at > latestSuccess) {
            latestSuccess = job.last_run.finished_at
          }
        }
      }

      if (!latestSuccess) return { status: "unknown" as const, label: "No data yet" }

      const ageMs = Date.now() - new Date(latestSuccess).getTime()
      const ageHours = ageMs / (1000 * 60 * 60)

      if (ageHours < 24) return { status: "fresh" as const, label: `${Math.round(ageHours)}h ago` }
      if (ageHours < 72) return { status: "stale" as const, label: `${Math.round(ageHours / 24)}d ago` }
      return { status: "old" as const, label: `${Math.round(ageHours / 24)}d ago` }
    },
  })
}
