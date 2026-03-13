import { useQuery } from "@tanstack/react-query"
import { apiClient } from "@/lib/api"

interface OperatorRankingEntry {
  operator: string
  total_incs: number
  inc_rate: number
  severe_count: number
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

export function useOperatorRanking(
  sortBy: string = "total_incs",
  order: string = "desc",
  limit?: number,
  page: number = 1
) {
  return useQuery({
    queryKey: ["operator-ranking", sortBy, order, limit, page],
    queryFn: () =>
      apiClient<ApiResponse<OperatorRankingEntry[]>>("/api/incs/operator-ranking", {
        params: {
          sort_by: sortBy,
          order,
          limit,
          page,
          page_size: limit ?? 20,
        },
      }),
  })
}
