import { TrendingUp, TrendingDown } from "lucide-react"
import { Card, CardContent } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import type { ReactNode } from "react"

interface MetricCardProps {
  title: string
  value: string | number
  change?: number
  changeDirection?: "up" | "down"
  format?: "number" | "currency" | "decimal" | "compact"
  icon?: ReactNode
  loading?: boolean
}

function formatValue(value: string | number, format: MetricCardProps["format"]): string {
  if (typeof value === "string") return value

  switch (format) {
    case "compact": {
      if (value >= 1_000_000_000) return `${(value / 1_000_000_000).toFixed(1)}B`
      if (value >= 1_000_000) return `${(value / 1_000_000).toFixed(1)}M`
      if (value >= 1_000) return `${(value / 1_000).toFixed(1)}K`
      return value.toLocaleString()
    }
    case "currency":
      return new Intl.NumberFormat("en-US", {
        style: "currency",
        currency: "USD",
        maximumFractionDigits: 0,
      }).format(value)
    case "decimal":
      return value.toLocaleString(undefined, {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2,
      })
    case "number":
    default:
      return value.toLocaleString()
  }
}

export function MetricCard({
  title,
  value,
  change,
  changeDirection,
  format = "number",
  icon,
  loading = false,
}: MetricCardProps) {
  if (loading) {
    return (
      <Card>
        <CardContent className="pt-2">
          <div className="flex items-center justify-between">
            <Skeleton className="h-4 w-24" />
            <Skeleton className="h-8 w-8 rounded-md" />
          </div>
          <Skeleton className="mt-3 h-8 w-20" />
          <Skeleton className="mt-2 h-4 w-32" />
        </CardContent>
      </Card>
    )
  }

  // Determine if the change is an improvement or deterioration
  // For safety metrics: fewer incidents = improvement (down is good)
  const isImprovement = changeDirection === "down"
  const isDeteriorating = changeDirection === "up"

  return (
    <Card
      className={
        isImprovement
          ? "border-green-200 bg-green-50/50 dark:border-green-900/50 dark:bg-green-950/20"
          : isDeteriorating
            ? "border-red-200 bg-red-50/50 dark:border-red-900/50 dark:bg-red-950/20"
            : ""
      }
    >
      <CardContent className="pt-2">
        <div className="flex items-center justify-between">
          <p className="text-sm font-medium text-muted-foreground">{title}</p>
          {icon && (
            <div className="rounded-md bg-muted p-2 text-muted-foreground">
              {icon}
            </div>
          )}
        </div>
        <div className="mt-2">
          <p className="text-2xl font-bold tracking-tight">
            {formatValue(value, format)}
          </p>
        </div>
        {change !== undefined && changeDirection && (
          <div className="mt-1 flex items-center gap-1">
            {isImprovement ? (
              <TrendingDown className="h-4 w-4 text-green-600 dark:text-green-400" />
            ) : isDeteriorating ? (
              <TrendingUp className="h-4 w-4 text-red-600 dark:text-red-400" />
            ) : null}
            <span
              className={`text-sm font-medium ${
                isImprovement
                  ? "text-green-600 dark:text-green-400"
                  : isDeteriorating
                    ? "text-red-600 dark:text-red-400"
                    : "text-muted-foreground"
              }`}
            >
              {Math.abs(change).toFixed(1)}% {isImprovement ? "decrease" : "increase"} YoY
            </span>
          </div>
        )}
      </CardContent>
    </Card>
  )
}
