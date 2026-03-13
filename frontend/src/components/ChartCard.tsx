import type { ReactNode } from "react"
import {
  Card,
  CardHeader,
  CardTitle,
  CardDescription,
  CardContent,
  CardAction,
} from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"

interface ChartCardProps {
  title: string
  description?: string
  children: ReactNode
  loading?: boolean
  className?: string
  action?: ReactNode
}

export function ChartCard({
  title,
  description,
  children,
  loading = false,
  className,
  action,
}: ChartCardProps) {
  return (
    <Card className={className}>
      <CardHeader>
        <CardTitle>{title}</CardTitle>
        {description && <CardDescription>{description}</CardDescription>}
        {action && <CardAction>{action}</CardAction>}
      </CardHeader>
      <CardContent>
        {loading ? (
          <div className="flex flex-col gap-3">
            <Skeleton className="h-[300px] w-full rounded-lg" />
          </div>
        ) : (
          children
        )}
      </CardContent>
    </Card>
  )
}
