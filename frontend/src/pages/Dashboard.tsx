import { AlertTriangle, ShieldAlert, Gauge, Droplets } from "lucide-react"
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts"
import { useOperator } from "@/contexts/OperatorContext"
import { useMetricsSummary, useNormalizedMetrics } from "@/hooks/useMetrics"
import { MetricCard } from "@/components/MetricCard"
import { ChartCard } from "@/components/ChartCard"
import { AIBriefingPanel } from "@/components/AIBriefingPanel"
import { RootCauseChart } from "@/components/RootCauseChart"

const CHART_COLORS = {
  operator: "#2563eb",
  gomAverage: "#dc2626",
}

function getChangeDirection(change: number): "up" | "down" | undefined {
  if (change > 0) return "up"
  if (change < 0) return "down"
  return undefined
}

export default function Dashboard() {
  const { selectedOperator } = useOperator()
  const {
    data: metricsData,
    isLoading: metricsLoading,
    isError: metricsError,
  } = useMetricsSummary(selectedOperator)

  const {
    data: normalizedData,
    isLoading: normalizedLoading,
    isError: normalizedError,
  } = useNormalizedMetrics(selectedOperator)

  const metrics = metricsData?.data
  const normalized = normalizedData?.data ?? []

  return (
    <div className="p-6 space-y-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">
          Safety Analytics Dashboard
        </h1>
        <p className="text-muted-foreground mt-1">
          {selectedOperator
            ? `Performance overview for ${selectedOperator}`
            : "Overview of Gulf of Mexico safety metrics, incident trends, and operator performance."}
        </p>
      </div>

      {/* Metrics Row */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <MetricCard
          title="Total Incidents"
          value={metrics?.total_incidents ?? 0}
          change={metrics ? Math.abs(metrics.yoy_incidents) : undefined}
          changeDirection={
            metrics ? getChangeDirection(metrics.yoy_incidents) : undefined
          }
          format="compact"
          icon={<AlertTriangle className="h-4 w-4" />}
          loading={metricsLoading}
        />
        <MetricCard
          title="Total INCs"
          value={metrics?.total_incs ?? 0}
          change={metrics ? Math.abs(metrics.yoy_incs) : undefined}
          changeDirection={
            metrics ? getChangeDirection(metrics.yoy_incs) : undefined
          }
          format="compact"
          icon={<ShieldAlert className="h-4 w-4" />}
          loading={metricsLoading}
        />
        <MetricCard
          title="Production Volume"
          value={metrics?.production_volume_boe ?? 0}
          change={metrics ? Math.abs(metrics.yoy_production) : undefined}
          changeDirection={
            metrics
              ? metrics.yoy_production > 0
                ? "up"
                : metrics.yoy_production < 0
                  ? "down"
                  : undefined
              : undefined
          }
          format="compact"
          icon={<Droplets className="h-4 w-4" />}
          loading={metricsLoading}
        />
        <MetricCard
          title="Incidents per M BOE"
          value={
            metrics?.incidents_per_million_boe !== undefined
              ? metrics.incidents_per_million_boe.toFixed(2)
              : "0.00"
          }
          change={
            metrics ? Math.abs(metrics.yoy_incidents_per_boe) : undefined
          }
          changeDirection={
            metrics
              ? getChangeDirection(metrics.yoy_incidents_per_boe)
              : undefined
          }
          icon={<Gauge className="h-4 w-4" />}
          loading={metricsLoading}
        />
      </div>

      {metricsError && (
        <div className="rounded-lg border border-destructive/50 bg-destructive/10 p-4 text-sm text-destructive">
          Failed to load metrics. The backend API may not be running.
        </div>
      )}

      {/* Step 2.4 — AI Safety Briefing Panel */}
      <AIBriefingPanel operator={selectedOperator} />

      {/* Charts Row — Trend + Root Cause side by side on large screens */}
      <div className="grid gap-6 lg:grid-cols-2">
        {/* Normalized Trend Chart */}
        <ChartCard
          title="Incidents per Million BOE"
          description={
            selectedOperator
              ? `Normalized safety performance for ${selectedOperator} vs. GoM average`
              : "Gulf of Mexico normalized incident trend over time"
          }
          loading={normalizedLoading}
        >
          {normalizedError ? (
            <div className="flex h-[300px] items-center justify-center text-sm text-muted-foreground">
              Failed to load trend data. The backend API may not be running.
            </div>
          ) : normalized.length === 0 ? (
            <div className="flex h-[300px] items-center justify-center text-sm text-muted-foreground">
              No normalized data available
              {selectedOperator ? ` for ${selectedOperator}` : ""}.
            </div>
          ) : (
            <ResponsiveContainer width="100%" height={350}>
              <LineChart
                data={normalized}
                margin={{ top: 5, right: 30, left: 20, bottom: 5 }}
              >
                <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
                <XAxis
                  dataKey="year"
                  className="text-xs"
                  tick={{ fill: "currentColor" }}
                />
                <YAxis
                  className="text-xs"
                  tick={{ fill: "currentColor" }}
                  label={{
                    value: "Incidents / M BOE",
                    angle: -90,
                    position: "insideLeft",
                    style: { fill: "currentColor", fontSize: 12 },
                  }}
                />
                <Tooltip
                  contentStyle={{
                    backgroundColor: "var(--color-popover)",
                    borderColor: "var(--color-border)",
                    borderRadius: "0.5rem",
                    color: "var(--color-popover-foreground)",
                  }}
                  formatter={(value: unknown) => [Number(value).toFixed(2), ""]}
                />
                <Legend />
                {selectedOperator && (
                  <Line
                    type="monotone"
                    dataKey="incidents_per_million_boe"
                    name={selectedOperator}
                    stroke={CHART_COLORS.operator}
                    strokeWidth={2}
                    dot={{ r: 3 }}
                    activeDot={{ r: 5 }}
                  />
                )}
                <Line
                  type="monotone"
                  dataKey="gom_average"
                  name="GoM Average"
                  stroke={CHART_COLORS.gomAverage}
                  strokeWidth={2}
                  strokeDasharray={selectedOperator ? "5 5" : undefined}
                  dot={{ r: 3 }}
                  activeDot={{ r: 5 }}
                />
              </LineChart>
            </ResponsiveContainer>
          )}
        </ChartCard>

        {/* Step 2.5 — Root Cause Breakdown Chart */}
        <RootCauseChart operator={selectedOperator} />
      </div>
    </div>
  )
}
