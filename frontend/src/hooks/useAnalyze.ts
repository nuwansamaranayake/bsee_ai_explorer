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
// Step 2.5 — Root Cause Categorization
// ---------------------------------------------------------------------------

interface CategorizeRequest {
  incident_ids?: number[]
  operator?: string | null
  year_start?: number
  year_end?: number
  batch_size?: number
  force?: boolean
}

interface CategorizeData {
  categorized: number
  skipped: number
  summary: Record<string, number>
  average_confidence: number
}

export function useCategorize() {
  return useMutation({
    mutationFn: (req: CategorizeRequest) =>
      apiClient<ApiResponse<CategorizeData>>("/api/analyze/categorize", {
        method: "POST",
        body: JSON.stringify(req),
      }),
  })
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
