import { useCallback, useState } from "react"
import { useMutation, useQuery } from "@tanstack/react-query"
import { apiClient } from "@/lib/api"

// ---------------------------------------------------------------------------
// Step 2.4 — AI Trend Analysis
// ---------------------------------------------------------------------------

interface TrendAnalysisRequest {
  operator?: string | null
  year_start?: number
  year_end?: number
  incident_types?: string[]
  water_depth_min?: number
  water_depth_max?: number
}

interface TrendAnalysisData {
  briefing: string
  data_summary: Record<string, unknown>
  operator: string
  date_range: string
  generated_at: string
}

interface ApiResponse<T> {
  data: T
  meta?: Record<string, unknown>
}

export function useTrendAnalysis() {
  return useMutation({
    mutationFn: (req: TrendAnalysisRequest) =>
      apiClient<ApiResponse<TrendAnalysisData>>("/api/analyze/trends", {
        method: "POST",
        body: JSON.stringify(req),
      }),
  })
}

// ---------------------------------------------------------------------------
// Step 2.5 — Root Cause Categorization (SSE streaming with progress)
// ---------------------------------------------------------------------------

interface CategorizeRequest {
  incident_ids?: number[]
  operator?: string | null
  year_start?: number
  year_end?: number
  batch_size?: number
  force?: boolean
}

interface CategorizeProgress {
  batch: number
  total_batches: number
  categorized: number
  message: string
}

interface CategorizeResult {
  categorized: number
  skipped: number
  summary: Record<string, number>
  average_confidence: number
}

/**
 * SSE-based categorize hook with real-time progress feedback.
 *
 * Instead of a single long-running POST, this streams progress events
 * from the backend as each batch of incidents is classified.
 */
export function useCategorize() {
  const [progress, setProgress] = useState<CategorizeProgress | null>(null)
  const [isPending, setIsPending] = useState(false)

  const categorize = useCallback(
    async (
      req: CategorizeRequest,
      callbacks?: {
        onSuccess?: (result: CategorizeResult) => void
        onError?: (error: Error) => void
      }
    ) => {
      setIsPending(true)
      setProgress(null)

      try {
        const API_BASE = import.meta.env.VITE_API_URL || ""
        const token = sessionStorage.getItem("beacon_token")
        const headers: Record<string, string> = {
          "Content-Type": "application/json",
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        }

        const response = await fetch(`${API_BASE}/api/analyze/categorize`, {
          method: "POST",
          headers,
          body: JSON.stringify(req),
        })

        // Handle non-streaming responses (no_data, all_categorized)
        const contentType = response.headers.get("content-type") || ""
        if (contentType.includes("application/json")) {
          const jsonData = await response.json()
          const status = jsonData?.meta?.status

          if (status === "no_data" || status === "all_categorized") {
            callbacks?.onSuccess?.({
              categorized: jsonData.data.categorized ?? 0,
              skipped: jsonData.data.skipped ?? 0,
              summary: jsonData.data.summary ?? {},
              average_confidence: jsonData.data.average_confidence ?? 0,
            })
            return
          }
        }

        if (!response.ok) {
          // Handle 401 — session expired
          if (response.status === 401) {
            sessionStorage.removeItem("beacon_token")
            sessionStorage.removeItem("beacon_user")
            if (!window.location.pathname.startsWith("/login")) {
              window.location.href = "/login"
            }
            throw new Error("Your session has expired. Please sign in again.")
          }
          const errData = await response.json().catch(() => ({}))
          const detail = errData?.detail
          throw new Error(typeof detail === "string" ? detail : "Categorization failed. Please try again.")
        }

        // Parse SSE stream
        const reader = response.body?.getReader()
        if (!reader) throw new Error("No response body")

        const decoder = new TextDecoder()
        let buffer = ""

        while (true) {
          const { done, value } = await reader.read()
          if (done) break

          buffer += decoder.decode(value, { stream: true })
          const lines = buffer.split("\n")
          buffer = lines.pop() || ""

          for (const line of lines) {
            if (!line.startsWith("data: ")) continue
            const jsonStr = line.slice(6).trim()
            if (!jsonStr) continue

            try {
              const event = JSON.parse(jsonStr)

              if (event.type === "progress") {
                setProgress({
                  batch: event.batch,
                  total_batches: event.total_batches,
                  categorized: event.categorized,
                  message: event.message,
                })
              } else if (event.type === "complete") {
                setProgress(null)
                callbacks?.onSuccess?.({
                  categorized: event.categorized,
                  skipped: event.skipped,
                  summary: event.summary,
                  average_confidence: event.average_confidence,
                })
              } else if (event.type === "error") {
                throw new Error(event.message || "AI categorization failed.")
              }
            } catch (parseErr) {
              if (parseErr instanceof Error && parseErr.message !== "AI categorization failed.") {
                // Skip malformed SSE events
                continue
              }
              throw parseErr
            }
          }
        }
      } catch (error) {
        setProgress(null)
        callbacks?.onError?.(error instanceof Error ? error : new Error("Categorization failed."))
      } finally {
        setIsPending(false)
      }
    },
    []
  )

  return { categorize, isPending, progress }
}

// ---------------------------------------------------------------------------
// Root Cause Summary (for chart)
// ---------------------------------------------------------------------------

interface RootCauseEntry {
  cause: string
  count: number
  avg_confidence: number
}

export function useRootCauses(
  operator: string | null,
  yearStart?: number,
  yearEnd?: number
) {
  return useQuery({
    queryKey: ["root-causes", operator, yearStart, yearEnd],
    queryFn: () =>
      apiClient<ApiResponse<RootCauseEntry[]>>("/api/analyze/root-causes", {
        params: {
          operator,
          year_start: yearStart,
          year_end: yearEnd,
        },
      }),
  })
}
