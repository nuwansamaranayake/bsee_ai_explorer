import { useQuery } from "@tanstack/react-query"
import { apiClient } from "@/lib/api"

export interface Operator {
  name: string
  incident_count: number
  inc_count: number
  platform_count: number
}

interface RawOperator {
  operator_name: string
  incident_count: number
  inc_count: number
  platform_count: number
}

interface ApiResponse<T> {
  data: T
  meta?: Record<string, unknown>
}

export function useOperators() {
  return useQuery({
    queryKey: ["operators"],
    queryFn: async () => {
      const raw = await apiClient<ApiResponse<RawOperator[]>>("/api/operators")
      return {
        ...raw,
        data: raw.data.map((op) => ({
          name: op.operator_name,
          incident_count: op.incident_count,
          inc_count: op.inc_count,
          platform_count: op.platform_count,
        })),
      } as ApiResponse<Operator[]>
    },
  })
}
