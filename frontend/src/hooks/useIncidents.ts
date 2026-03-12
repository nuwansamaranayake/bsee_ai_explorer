import { useQuery } from "@tanstack/react-query"
import { apiClient } from "@/lib/api"

interface Incident {
  id: string
  date: string
  operator: string
  description: string
  severity: string
}

interface ApiResponse<T> {
  data: T
  meta?: Record<string, unknown>
}

interface UseIncidentsParams {
  operator?: string
  startDate?: string
  endDate?: string
  page?: number
  pageSize?: number
}

export function useIncidents(params: UseIncidentsParams = {}) {
  const queryParams: Record<string, string> = {}
  if (params.operator) queryParams.operator = params.operator
  if (params.startDate) queryParams.start_date = params.startDate
  if (params.endDate) queryParams.end_date = params.endDate
  if (params.page) queryParams.page = String(params.page)
  if (params.pageSize) queryParams.page_size = String(params.pageSize)

  return useQuery({
    queryKey: ["incidents", params],
    queryFn: () =>
      apiClient<ApiResponse<Incident[]>>("/api/incidents", {
        params: queryParams,
      }),
  })
}
