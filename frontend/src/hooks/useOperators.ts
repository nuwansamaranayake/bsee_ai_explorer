import { useQuery } from "@tanstack/react-query"
import { apiClient } from "@/lib/api"

interface Operator {
  id: string
  name: string
  incident_count: number
  inc_count: number
}

interface ApiResponse<T> {
  data: T
  meta?: Record<string, unknown>
}

export function useOperators() {
  return useQuery({
    queryKey: ["operators"],
    queryFn: () => apiClient<ApiResponse<Operator[]>>("/api/operators"),
  })
}
