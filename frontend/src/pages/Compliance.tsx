import { useState, useMemo } from "react"
import {
  PieChart,
  Pie,
  Cell,
  AreaChart,
  Area,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts"
import {
  ChevronUp,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  ShieldCheck,
  ShieldAlert,
} from "lucide-react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { ChartCard } from "@/components/ChartCard"
import { useOperator } from "@/contexts/OperatorContext"
import { useINCSummary } from "@/hooks/useINCSummary"
import { useOperatorRanking } from "@/hooks/useOperatorRanking"

const PIE_COLORS = ["#f59e0b", "#dc2626", "#7c3aed"]
const CHART_COLORS = {
  operator: "#2563eb",
  gomAverage: "#dc2626",
}

type SortColumn = "operator" | "total_incs" | "inc_rate" | "severe_count"
type SortOrder = "asc" | "desc"

export default function Compliance() {
  const { selectedOperator, setSelectedOperator } = useOperator()
  const [tableSortBy, setTableSortBy] = useState<SortColumn>("total_incs")
  const [tableSortOrder, setTableSortOrder] = useState<SortOrder>("desc")
  const [tablePage, setTablePage] = useState(1)
  const PAGE_SIZE = 20

  const {
    data: incSummaryData,
    isLoading: incSummaryLoading,
    isError: incSummaryError,
  } = useINCSummary(selectedOperator)

  const {
    data: rankingData,
    isLoading: rankingLoading,
    isError: rankingError,
  } = useOperatorRanking(tableSortBy, tableSortOrder, PAGE_SIZE, tablePage)

  const summary = incSummaryData?.data
  const rankingEntries = rankingData?.data ?? []
  const rankingMeta = rankingData?.meta

  // Determine benchmark status
  const isBelowAverage = summary
    ? summary.total_incs <= summary.gom_average
    : false

  // Sort handler for table columns
  function handleSort(column: SortColumn) {
    if (tableSortBy === column) {
      setTableSortOrder((prev) => (prev === "asc" ? "desc" : "asc"))
    } else {
      setTableSortBy(column)
      setTableSortOrder("desc")
    }
    setTablePage(1)
  }

  function SortIcon({ column }: { column: SortColumn }) {
    if (tableSortBy !== column) {
      return <ChevronUp className="inline h-3 w-3 text-muted-foreground/30" />
    }
    return tableSortOrder === "asc" ? (
      <ChevronUp className="inline h-3 w-3" />
    ) : (
      <ChevronDown className="inline h-3 w-3" />
    )
  }

  // Memoize year trend data for the area chart
  const yearTrendData = useMemo(() => {
    if (!summary) return []
    const operatorByYear = summary.by_year ?? []
    const gomByYear = summary.gom_by_year ?? []

    const yearMap = new Map<number, { year: number; operator: number; gom_average: number }>()

    for (const entry of gomByYear) {
      yearMap.set(entry.year, {
        year: entry.year,
        operator: 0,
        gom_average: entry.count,
      })
    }
    for (const entry of operatorByYear) {
      const existing = yearMap.get(entry.year)
      if (existing) {
        existing.operator = entry.count
      } else {
        yearMap.set(entry.year, {
          year: entry.year,
          operator: entry.count,
          gom_average: 0,
        })
      }
    }

    return Array.from(yearMap.values()).sort((a, b) => a.year - b.year)
  }, [summary])

  const totalPages = rankingMeta?.total_pages ?? 1

  return (
    <div className="p-6 space-y-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">
          Compliance Scorecard
        </h1>
        <p className="text-muted-foreground mt-1">
          {selectedOperator
            ? `Violation and compliance analysis for ${selectedOperator}`
            : "Track operator compliance ratings, violation history, and regulatory standing across the GoM."}
        </p>
      </div>

      {/* Benchmark Header Card */}
      {incSummaryLoading ? (
        <Card>
          <CardContent className="pt-4">
            <div className="flex items-center gap-4">
              <Skeleton className="h-12 w-12 rounded-full" />
              <div className="space-y-2">
                <Skeleton className="h-6 w-48" />
                <Skeleton className="h-4 w-64" />
              </div>
            </div>
          </CardContent>
        </Card>
      ) : incSummaryError ? (
        <Card className="border-destructive/50 bg-destructive/10">
          <CardContent className="pt-4">
            <p className="text-sm text-destructive">
              Failed to load compliance summary. The backend API may not be running.
            </p>
          </CardContent>
        </Card>
      ) : summary ? (
        <Card
          className={
            isBelowAverage
              ? "border-green-200 bg-green-50/50 dark:border-green-900/50 dark:bg-green-950/20"
              : "border-red-200 bg-red-50/50 dark:border-red-900/50 dark:bg-red-950/20"
          }
        >
          <CardContent className="pt-4">
            <div className="flex items-center gap-4">
              <div
                className={`rounded-full p-3 ${
                  isBelowAverage
                    ? "bg-green-100 text-green-700 dark:bg-green-900/50 dark:text-green-400"
                    : "bg-red-100 text-red-700 dark:bg-red-900/50 dark:text-red-400"
                }`}
              >
                {isBelowAverage ? (
                  <ShieldCheck className="h-6 w-6" />
                ) : (
                  <ShieldAlert className="h-6 w-6" />
                )}
              </div>
              <div>
                <div className="flex items-center gap-3">
                  <h2 className="text-xl font-semibold">
                    {selectedOperator ?? "All GoM"}: {summary.total_incs.toLocaleString()} INCs
                  </h2>
                  <Badge
                    variant={isBelowAverage ? "secondary" : "destructive"}
                  >
                    GoM Avg: {Math.round(summary.gom_average).toLocaleString()}
                  </Badge>
                </div>
                <p
                  className={`text-sm mt-1 ${
                    isBelowAverage
                      ? "text-green-700 dark:text-green-400"
                      : "text-red-700 dark:text-red-400"
                  }`}
                >
                  {isBelowAverage
                    ? `Better than ${summary.percentile_rank}% of GoM operators`
                    : `Worse than ${100 - summary.percentile_rank}% of GoM operators`}
                </p>
              </div>
            </div>
          </CardContent>
        </Card>
      ) : null}

      {/* Charts Grid */}
      <div className="grid gap-6 lg:grid-cols-2">
        {/* Severity Breakdown Pie Chart */}
        <ChartCard
          title="Severity Breakdown"
          description="Distribution of violation severity levels"
          loading={incSummaryLoading}
        >
          {incSummaryError ? (
            <div className="flex h-[300px] items-center justify-center text-sm text-muted-foreground">
              Failed to load severity data.
            </div>
          ) : !summary?.severity_breakdown?.length ? (
            <div className="flex h-[300px] items-center justify-center text-sm text-muted-foreground">
              No severity data available.
            </div>
          ) : (
            <ResponsiveContainer width="100%" height={300}>
              <PieChart>
                <Pie
                  data={summary.severity_breakdown}
                  dataKey="count"
                  nameKey="severity"
                  cx="50%"
                  cy="50%"
                  outerRadius={100}
                  label={({ name, percent }: { name?: string; percent?: number }) =>
                    `${name ?? ''}: ${((percent ?? 0) * 100).toFixed(0)}%`
                  }
                  labelLine={true}
                >
                  {summary.severity_breakdown.map((_entry, index) => (
                    <Cell
                      key={`cell-${index}`}
                      fill={PIE_COLORS[index % PIE_COLORS.length]}
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
                />
                <Legend />
              </PieChart>
            </ResponsiveContainer>
          )}
        </ChartCard>

        {/* Violations Per Year Area Chart */}
        <ChartCard
          title="Violations Per Year"
          description={
            selectedOperator
              ? `Annual INCs for ${selectedOperator} vs. GoM average`
              : "Annual INC trend across the Gulf of Mexico"
          }
          loading={incSummaryLoading}
        >
          {incSummaryError ? (
            <div className="flex h-[300px] items-center justify-center text-sm text-muted-foreground">
              Failed to load annual data.
            </div>
          ) : yearTrendData.length === 0 ? (
            <div className="flex h-[300px] items-center justify-center text-sm text-muted-foreground">
              No annual violation data available.
            </div>
          ) : (
            <ResponsiveContainer width="100%" height={300}>
              <AreaChart
                data={yearTrendData}
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
                />
                <Tooltip
                  contentStyle={{
                    backgroundColor: "var(--color-popover)",
                    borderColor: "var(--color-border)",
                    borderRadius: "0.5rem",
                    color: "var(--color-popover-foreground)",
                  }}
                />
                <Legend />
                {selectedOperator && (
                  <Area
                    type="monotone"
                    dataKey="operator"
                    name={selectedOperator}
                    stroke={CHART_COLORS.operator}
                    fill={CHART_COLORS.operator}
                    fillOpacity={0.15}
                    strokeWidth={2}
                  />
                )}
                <Area
                  type="monotone"
                  dataKey="gom_average"
                  name="GoM Average"
                  stroke={CHART_COLORS.gomAverage}
                  fill={CHART_COLORS.gomAverage}
                  fillOpacity={0.05}
                  strokeWidth={2}
                  strokeDasharray={selectedOperator ? "5 5" : undefined}
                />
              </AreaChart>
            </ResponsiveContainer>
          )}
        </ChartCard>

        {/* Top Violations by Component */}
        <ChartCard
          title="Top Violations by Component"
          description="Most frequently cited equipment and components"
          loading={incSummaryLoading}
          className="lg:col-span-2"
        >
          {incSummaryError ? (
            <div className="flex h-[300px] items-center justify-center text-sm text-muted-foreground">
              Failed to load component data.
            </div>
          ) : !summary?.top_components?.length ? (
            <div className="flex h-[300px] items-center justify-center text-sm text-muted-foreground">
              No component data available.
            </div>
          ) : (
            <ResponsiveContainer width="100%" height={350}>
              <BarChart
                data={summary.top_components}
                layout="vertical"
                margin={{ top: 5, right: 30, left: 120, bottom: 5 }}
              >
                <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
                <XAxis
                  type="number"
                  className="text-xs"
                  tick={{ fill: "currentColor" }}
                />
                <YAxis
                  type="category"
                  dataKey="component"
                  width={110}
                  className="text-xs"
                  tick={{ fill: "currentColor" }}
                />
                <Tooltip
                  contentStyle={{
                    backgroundColor: "var(--color-popover)",
                    borderColor: "var(--color-border)",
                    borderRadius: "0.5rem",
                    color: "var(--color-popover-foreground)",
                  }}
                />
                <Bar dataKey="count" name="INCs" fill="#2563eb" radius={[0, 4, 4, 0]} />
              </BarChart>
            </ResponsiveContainer>
          )}
        </ChartCard>
      </div>

      {/* Operator Ranking Table */}
      <Card>
        <CardHeader>
          <CardTitle>Operator Ranking</CardTitle>
        </CardHeader>
        <CardContent>
          {rankingLoading ? (
            <div className="space-y-3">
              {Array.from({ length: 10 }).map((_, i) => (
                <Skeleton key={i} className="h-10 w-full" />
              ))}
            </div>
          ) : rankingError ? (
            <div className="text-sm text-muted-foreground py-8 text-center">
              Failed to load operator rankings. The backend API may not be running.
            </div>
          ) : rankingEntries.length === 0 ? (
            <div className="text-sm text-muted-foreground py-8 text-center">
              No operator ranking data available.
            </div>
          ) : (
            <>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b text-left">
                      <th
                        className="cursor-pointer px-3 py-3 font-medium text-muted-foreground hover:text-foreground"
                        onClick={() => handleSort("operator")}
                      >
                        Operator <SortIcon column="operator" />
                      </th>
                      <th
                        className="cursor-pointer px-3 py-3 text-right font-medium text-muted-foreground hover:text-foreground"
                        onClick={() => handleSort("total_incs")}
                      >
                        Total INCs <SortIcon column="total_incs" />
                      </th>
                      <th
                        className="cursor-pointer px-3 py-3 text-right font-medium text-muted-foreground hover:text-foreground"
                        onClick={() => handleSort("inc_rate")}
                      >
                        INC Rate <SortIcon column="inc_rate" />
                      </th>
                      <th
                        className="cursor-pointer px-3 py-3 text-right font-medium text-muted-foreground hover:text-foreground"
                        onClick={() => handleSort("severe_count")}
                      >
                        Severe <SortIcon column="severe_count" />
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {rankingEntries.map((entry) => {
                      const isSelected =
                        selectedOperator === entry.operator
                      return (
                        <tr
                          key={entry.operator}
                          className={`border-b transition-colors hover:bg-muted/50 cursor-pointer ${
                            isSelected
                              ? "bg-primary/5 font-medium"
                              : ""
                          }`}
                          onClick={() =>
                            setSelectedOperator(
                              isSelected ? null : entry.operator
                            )
                          }
                        >
                          <td className="px-3 py-3">
                            <div className="flex items-center gap-2">
                              {isSelected && (
                                <div className="h-2 w-2 rounded-full bg-primary" />
                              )}
                              <span className={isSelected ? "text-primary" : ""}>
                                {entry.operator}
                              </span>
                            </div>
                          </td>
                          <td className="px-3 py-3 text-right tabular-nums">
                            {entry.total_incs.toLocaleString()}
                          </td>
                          <td className="px-3 py-3 text-right tabular-nums">
                            {entry.inc_rate.toFixed(2)}
                          </td>
                          <td className="px-3 py-3 text-right">
                            {entry.severe_count > 0 ? (
                              <Badge variant="destructive">
                                {entry.severe_count.toLocaleString()}
                              </Badge>
                            ) : (
                              <span className="text-muted-foreground">0</span>
                            )}
                          </td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>

              {/* Pagination */}
              <div className="mt-4 flex items-center justify-between">
                <p className="text-sm text-muted-foreground">
                  Page {tablePage} of {totalPages}
                </p>
                <div className="flex items-center gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={tablePage <= 1}
                    onClick={() => setTablePage((p) => Math.max(1, p - 1))}
                  >
                    <ChevronLeft className="h-4 w-4" />
                    Previous
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={tablePage >= totalPages}
                    onClick={() =>
                      setTablePage((p) => Math.min(totalPages, p + 1))
                    }
                  >
                    Next
                    <ChevronRight className="h-4 w-4" />
                  </Button>
                </div>
              </div>
            </>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
