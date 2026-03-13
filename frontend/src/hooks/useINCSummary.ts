import { useQuery } from "@tanstack/react-query"
import { apiClient } from "@/lib/api"

interface INCSeverityBreakdown {
  severity: string
  count: number
}

interface INCSummaryByYear {
  year: number
  count: number
}

interface INCTopComponent {
  component: string
  count: number
}

interface INCSummaryData {
  total_incs: number
  gom_average: number
  percentile_rank: number
  severity_breakdown: INCSeverityBreakdown[]
  by_year: INCSummaryByYear[]
  gom_by_year: INCSummaryByYear[]
  top_components: INCTopComponent[]
}

interface ApiResponse<T> {
  data: T
  meta?: Record<string, unknown>
}

export function useINCSummary(operator: string | null) {
  return useQuery({
    queryKey: ["incs-summary", operator],
    queryFn: () =>
      apiClient<ApiResponse<INCSummaryData>>("/api/incs/summary", {
        params: { operator },
      }),
  })
}
