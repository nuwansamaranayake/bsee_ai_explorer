import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { apiClient } from "@/lib/api"

interface Alert {
  id: number
  alert_number: string
  title: string
  published_date: string
  source_url: string
  status: string
  has_digest: boolean
  ai_summary: string | null
  ai_impact: string | null
  ai_action_items: string[]
  created_at: string
}

interface AlertDetail extends Alert {
  pdf_url: string
  raw_text: string | null
  updated_at: string
}

interface AlertStats {
  total: number
  new: number
  reviewed: number
  dismissed: number
}

interface ApiResponse<T> {
  data: T
  meta?: Record<string, unknown>
}

export function useAlerts(status?: string, limit = 20, offset = 0) {
  return useQuery({
    queryKey: ["regulatory", "alerts", status, limit, offset],
    queryFn: () =>
      apiClient<ApiResponse<Alert[]>>("/api/regulatory/alerts", {
        params: { status: status || undefined, limit, offset },
      }),
  })
}

export function useAlertDetail(alertId: number | null) {
  return useQuery({
    queryKey: ["regulatory", "alert", alertId],
    queryFn: () =>
      apiClient<ApiResponse<AlertDetail>>(`/api/regulatory/alerts/${alertId}`),
    enabled: alertId !== null,
  })
}

export function useAlertStats() {
  return useQuery({
    queryKey: ["regulatory", "stats"],
    queryFn: () => apiClient<ApiResponse<AlertStats>>("/api/regulatory/stats"),
  })
}

export function useGenerateDigest() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (alertId: number) =>
      apiClient<ApiResponse<Record<string, unknown>>>(
        `/api/regulatory/alerts/${alertId}/digest`,
        { method: "POST" }
      ),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["regulatory"] })
    },
  })
}

export function useUpdateAlertStatus() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ alertId, status }: { alertId: number; status: string }) =>
      apiClient<ApiResponse<{ id: number; status: string }>>(
        `/api/regulatory/alerts/${alertId}/status`,
        {
          method: "PATCH",
          body: JSON.stringify({ status }),
        }
      ),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["regulatory"] })
    },
  })
}

export function useTriggerScrape() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: () =>
      apiClient<ApiResponse<{ new_alerts: number }>>("/api/regulatory/scrape", {
        method: "POST",
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["regulatory"] })
    },
  })
}
