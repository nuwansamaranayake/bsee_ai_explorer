import { useState } from "react"
import {
  PieChart,
  Pie,
  Cell,
  ResponsiveContainer,
  Tooltip,
  Legend,
} from "recharts"
import { Zap, RefreshCw, AlertCircle } from "lucide-react"
import { Button } from "@/components/ui/button"
import { ChartCard } from "@/components/ChartCard"
import { useRootCauses, useCategorize } from "@/hooks/useAnalyze"
import { useQueryClient } from "@tanstack/react-query"

const CAUSE_COLORS: Record<string, string> = {
  equipment_failure: "#ef4444",
  human_error: "#f97316",
  procedural_gap: "#eab308",
  weather_event: "#06b6d4",
  corrosion: "#8b5cf6",
  design_flaw: "#ec4899",
  maintenance_failure: "#f43f5e",
  communication_failure: "#14b8a6",
  third_party: "#6366f1",
  unknown: "#94a3b8",
}

const CAUSE_LABELS: Record<string, string> = {
  equipment_failure: "Equipment Failure",
  human_error: "Human Error",
  procedural_gap: "Procedural Gap",
  weather_event: "Weather Event",
  corrosion: "Corrosion",
  design_flaw: "Design Flaw",
  maintenance_failure: "Maintenance Failure",
  communication_failure: "Communication Failure",
  third_party: "Third Party",
  unknown: "Unknown",
}

interface RootCauseChartProps {
  operator: string | null
}

export function RootCauseChart({ operator }: RootCauseChartProps) {
  const [categorizeStatus, setCategorizeStatus] = useState<string | null>(null)
  const queryClient = useQueryClient()

  const {
    data: rootCausesData,
    isLoading,
    isError,
  } = useRootCauses(operator)

  const {
    categorize,
    isPending: isCategorizing,
    progress,
  } = useCategorize()

  const rootCauses = rootCausesData?.data ?? []

  const chartData = rootCauses.map((rc) => ({
    name: CAUSE_LABELS[rc.cause] || rc.cause,
    value: rc.count,
    confidence: rc.avg_confidence,
    cause: rc.cause,
  }))

  const handleCategorize = () => {
    setCategorizeStatus(null)
    categorize(
      {
        operator: operator || undefined,
        batch_size: 10,
      },
      {
        onSuccess: (result) => {
          if (result.categorized === 0 && result.skipped > 0) {
            setCategorizeStatus(
              `All ${result.skipped} incidents are already categorized. Use force mode to re-classify.`
            )
          } else {
            setCategorizeStatus(
              `Categorized ${result.categorized} incidents` +
              (result.skipped > 0 ? ` (${result.skipped} already done)` : "") +
              `. Avg confidence: ${(result.average_confidence * 100).toFixed(0)}%`
            )
          }
          // Refetch root causes chart
          queryClient.invalidateQueries({ queryKey: ["root-causes"] })
        },
        onError: (error) => {
          setCategorizeStatus(
            `Failed: ${error.message}`
          )
        },
      }
    )
  }

  const renderCustomLabel = ({ name, percent }: { name?: string; percent?: number }) => {
    if (!percent || percent < 0.05) return null
    return `${name} ${((percent ?? 0) * 100).toFixed(0)}%`
  }

  // Progress bar percentage
  const progressPct = progress
    ? Math.round((progress.batch / Math.max(progress.total_batches, 1)) * 100)
    : 0

  return (
    <ChartCard
      title="Root Cause Breakdown"
      description={
        operator
          ? `AI-categorized root causes for ${operator}`
          : "AI-categorized root causes across all GoM incidents"
      }
      loading={isLoading}
      action={
        <Button
          variant="outline"
          size="sm"
          onClick={handleCategorize}
          disabled={isCategorizing}
          className="h-8 gap-1.5"
        >
          {isCategorizing ? (
            <>
              <RefreshCw className="h-3.5 w-3.5 animate-spin" />
              Categorizing...
            </>
          ) : (
            <>
              <Zap className="h-3.5 w-3.5" />
              Categorize Incidents
            </>
          )}
        </Button>
      }
    >
      {/* Live progress indicator */}
      {isCategorizing && progress && (
        <div className="mb-3 space-y-2">
          <div className="flex items-center gap-2 text-xs text-muted-foreground">
            <RefreshCw className="h-3 w-3 animate-spin shrink-0" />
            <span>{progress.message}</span>
          </div>
          <div className="w-full bg-muted rounded-full h-2 overflow-hidden">
            <div
              className="bg-primary h-full rounded-full transition-all duration-500 ease-out"
              style={{ width: `${progressPct}%` }}
            />
          </div>
          <div className="flex justify-between text-xs text-muted-foreground">
            <span>Batch {progress.batch} of {progress.total_batches}</span>
            <span>{progress.categorized} categorized so far</span>
          </div>
        </div>
      )}

      {/* Status message after completion */}
      {categorizeStatus && !isCategorizing && (
        <div className={`mb-3 rounded-md px-3 py-2 text-xs ${
          categorizeStatus.startsWith("Failed")
            ? "bg-destructive/10 text-destructive"
            : "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400"
        }`}>
          {categorizeStatus}
        </div>
      )}

      {isError ? (
        <div className="flex h-[300px] items-center justify-center gap-2 text-sm text-muted-foreground">
          <AlertCircle className="h-4 w-4" />
          Failed to load root cause data.
        </div>
      ) : chartData.length === 0 ? (
        <div className="flex h-[300px] flex-col items-center justify-center gap-3 text-muted-foreground">
          <Zap className="h-8 w-8 opacity-50" />
          <div className="text-center">
            <p className="text-sm font-medium">No root causes categorized yet</p>
            <p className="text-xs mt-1">
              Click &quot;Categorize Incidents&quot; to run AI classification
              {operator ? ` for ${operator}` : ""}.
            </p>
          </div>
        </div>
      ) : (
        <ResponsiveContainer width="100%" height={350}>
          <PieChart>
            <Pie
              data={chartData}
              cx="50%"
              cy="50%"
              outerRadius={120}
              innerRadius={60}
              paddingAngle={2}
              dataKey="value"
              label={renderCustomLabel}
              labelLine={false}
            >
              {chartData.map((entry) => (
                <Cell
                  key={entry.cause}
                  fill={CAUSE_COLORS[entry.cause] || "#94a3b8"}
                  stroke="transparent"
                />
              ))}
            </Pie>
            <Tooltip
              contentStyle={{
                backgroundColor: "var(--color-popover)",
                borderColor: "var(--color-border)",
                borderRadius: "0.5rem",
                color: "var(--color-popover-foreground)",
              }}
              formatter={(value: unknown, name: unknown) => [
                `${value} incidents`,
                String(name),
              ]}
            />
            <Legend
              verticalAlign="bottom"
              height={36}
              formatter={(value: string) => (
                <span className="text-xs">{value}</span>
              )}
            />
          </PieChart>
        </ResponsiveContainer>
      )}
    </ChartCard>
  )
}
