import { useMutation, useQuery } from "@tanstack/react-query"
import { apiClient } from "@/lib/api"

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface Citation {
  source_file: string
  title: string
  page_number: number
  relevance_score: number
  excerpt: string
}

interface DocumentSearchResponse {
  answer: string
  citations: Citation[]
  query: string
  doc_count: number
  generated_at: string
}

interface DocumentStats {
  total_documents: number
  total_chunks: number
  safety_alerts: number
  investigation_reports: number
  oldest_date: string | null
  newest_date: string | null
}

interface ApiResponse<T> {
  data: T
  meta?: Record<string, unknown>
}

// ---------------------------------------------------------------------------
// Hooks
// ---------------------------------------------------------------------------

export function useDocumentSearch() {
  return useMutation({
    mutationFn: (params: { query: string; top_k?: number; doc_type?: string | null }) =>
      apiClient<ApiResponse<DocumentSearchResponse>>("/api/documents/search", {
        method: "POST",
        body: JSON.stringify({
          query: params.query,
          top_k: params.top_k ?? 5,
          doc_type: params.doc_type ?? undefined,
        }),
      }),
  })
}

export function useDocumentStats() {
  return useQuery({
    queryKey: ["document-stats"],
    queryFn: () => apiClient<ApiResponse<DocumentStats>>("/api/documents/stats"),
    staleTime: 5 * 60 * 1000,
  })
}

export type { Citation, DocumentSearchResponse, DocumentStats }
