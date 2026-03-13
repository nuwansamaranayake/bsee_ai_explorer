import { useQuery } from "@tanstack/react-query"
import { apiClient } from "@/lib/api"

interface Incident {
  id: string
  date: string
  operator: string
  description: string
  severity: string
  incident_type?: string
  cause?: string
  water_depth?: number
  root_cause?: string
}

interface ApiResponse<T> {
  data: T
  meta?: {
    total: number
    page: number
    page_size: number
    total_pages: number
  }
}

interface UseIncidentsParams {
  operator?: string | null
  startDate?: string
  endDate?: string
  page?: number
  pageSize?: number
  incidentType?: string
  cause?: string
  waterDepthMin?: number
  waterDepthMax?: number
  rootCause?: string
}

export function useIncidents(params: UseIncidentsParams = {}) {
  return useQuery({
    queryKey: ["incidents", params],
    queryFn: () =>
      apiClient<ApiResponse<Incident[]>>("/api/incidents", {
        params: {
          operator: params.operator,
          start_date: params.startDate,
          end_date: params.endDate,
          page: params.page,
          page_size: params.pageSize,
          incident_type: params.incidentType,
          cause: params.cause,
          water_depth_min: params.waterDepthMin,
          water_depth_max: params.waterDepthMax,
          root_cause: params.rootCause,
        },
      }),
  })
}
