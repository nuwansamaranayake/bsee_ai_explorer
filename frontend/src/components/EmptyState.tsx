import type { ReactNode } from "react"
import { Inbox, Search, FileQuestion } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"

interface EmptyStateProps {
  /** Primary message */
  message?: string
  /** Optional description with guidance */
  description?: string
  /** Optional icon — defaults to Inbox */
  icon?: ReactNode
  /** Optional action button label */
  actionLabel?: string
  /** Optional action button callback */
  onAction?: () => void
  /** Variant for common empty state patterns */
  variant?: "default" | "search" | "no-data"
  /** Optional className */
  className?: string
}

const DEFAULT_ICONS = {
  default: <Inbox className="h-8 w-8 text-muted-foreground" />,
  search: <Search className="h-8 w-8 text-muted-foreground" />,
  "no-data": <FileQuestion className="h-8 w-8 text-muted-foreground" />,
}

/**
 * Reusable empty state component — consistent display for when there's
 * no data to show. Always provides helpful guidance to the user.
 */
export function EmptyState({
  message = "No data available",
  description,
  icon,
  actionLabel,
  onAction,
  variant = "default",
  className = "",
}: EmptyStateProps) {
  const displayIcon = icon || DEFAULT_ICONS[variant]

  return (
    <Card className={`border-dashed ${className}`}>
      <CardContent className="flex flex-col items-center justify-center py-12 text-center">
        <div className="mb-4">{displayIcon}</div>
        <h3 className="text-base font-medium mb-1">{message}</h3>
        {description && (
          <p className="text-sm text-muted-foreground max-w-md mb-4">
            {description}
          </p>
        )}
        {actionLabel && onAction && (
          <Button variant="outline" size="sm" onClick={onAction}>
            {actionLabel}
          </Button>
        )}
      </CardContent>
    </Card>
  )
}

export default EmptyState
