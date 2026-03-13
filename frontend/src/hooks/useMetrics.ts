import { useQuery } from "@tanstack/react-query"
import { apiClient } from "@/lib/api"

// ---------------------------------------------------------------------------
// Raw API response types (match the actual backend responses)
// ---------------------------------------------------------------------------

interface KPI {
  value: number
  yoy_change: number
  direction: "up" | "down" | "flat"
}

interface RawMetricsSummary {
  total_incidents: KPI
  total_incs: KPI
  total_production_boe: KPI
  incidents_per_million_boe: KPI
}

interface RawNormalizedEntry {
  operator_name: string
  year: number
  total_boe: number
  incidents: number
  fatalities: number
  incs: number
  incidents_per_million_boe: number
  incs_per_million_boe: number
  fatalities_per_million_boe: number
}

interface GomAverages {
  total_boe: number
  total_incidents: number
  total_incs: number
  total_fatalities: number
  incidents_per_million_boe: number
  incs_per_million_boe: number
  fatalities_per_million_boe: number
}

interface NormalizedMeta {
  total: number
  gom_averages: GomAverages
  operator: string
}

// ---------------------------------------------------------------------------
// Transformed types for Dashboard consumption
// ---------------------------------------------------------------------------

export interface MetricsSummaryData {
  total_incidents: number
  total_incs: number
  production_volume_boe: number
  incidents_per_million_boe: number
  yoy_incidents: number
  yoy_incs: number
  yoy_production: number
  yoy_incidents_per_boe: number
}

export interface NormalizedMetricsEntry {
  year: number
  incidents_per_million_boe: number
  gom_average: number
}

interface ApiResponse<T> {
  data: T
  meta?: Record<string, unknown>
}

// ---------------------------------------------------------------------------
// Hooks
// ---------------------------------------------------------------------------

export function useMetricsSummary(operator: string | null) {
  return useQuery({
    queryKey: ["metrics-summary", operator],
    queryFn: async () => {
      const raw = await apiClient<{ data: RawMetricsSummary; meta: Record<string, unknown> }>(
        "/api/metrics/summary",
        { params: { operator } }
      )

      // Transform KPI structure to flat format expected by Dashboard
      const d = raw.data
      const transformed: MetricsSummaryData = {
        total_incidents: d.total_incidents.value,
        total_incs: d.total_incs.value,
        production_volume_boe: d.total_production_boe.value,
        incidents_per_million_boe: d.incidents_per_million_boe.value,
        yoy_incidents: d.total_incidents.yoy_change,
        yoy_incs: d.total_incs.yoy_change,
        yoy_production: d.total_production_boe.yoy_change,
        yoy_incidents_per_boe: d.incidents_per_million_boe.yoy_change,
      }

      return { data: transformed, meta: raw.meta } as ApiResponse<MetricsSummaryData>
    },
  })
}

export function useNormalizedMetrics(
  operator: string | null,
  yearStart?: number,
  yearEnd?: number
) {
  return useQuery({
    queryKey: ["normalized-metrics", operator, yearStart, yearEnd],
    queryFn: async () => {
      const raw = await apiClient<{
        data: RawNormalizedEntry[]
        meta: NormalizedMeta
      }>("/api/metrics/normalized", {
        params: {
          operator,
          year_start: yearStart,
          year_end: yearEnd,
        },
      })

      const gomAvg = raw.meta.gom_averages

      // Group by year and compute averages for the chart
      const yearMap = new Map<number, { totalRate: number; count: number }>()
      for (const entry of raw.data) {
        const existing = yearMap.get(entry.year) || { totalRate: 0, count: 0 }
        existing.totalRate += entry.incidents_per_million_boe
        existing.count += 1
        yearMap.set(entry.year, existing)
      }

      // If filtering by operator, compute per-year GoM averages from unfiltered data
      // Otherwise, just aggregate all entries per year
      const transformed: NormalizedMetricsEntry[] = []
      const years = [...yearMap.keys()].sort()

      if (operator) {
        // When filtering by operator, we have per-operator entries
        // Show operator's rate + GoM overall average
        for (const entry of raw.data) {
          transformed.push({
            year: entry.year,
            incidents_per_million_boe: entry.incidents_per_million_boe,
            gom_average: gomAvg.incidents_per_million_boe,
          })
        }
      } else {
        // GoM-wide: aggregate all operators per year into averages
        for (const year of years) {
          const agg = yearMap.get(year)!
          transformed.push({
            year,
            incidents_per_million_boe: 0, // Not used when no operator selected
            gom_average: agg.count > 0
              ? Number((agg.totalRate / agg.count).toFixed(4))
              : 0,
          })
        }
      }

      return { data: transformed, meta: raw.meta as unknown as Record<string, unknown> } as ApiResponse<NormalizedMetricsEntry[]>
    },
  })
}
