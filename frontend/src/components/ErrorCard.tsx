import { AlertCircle, RefreshCw, WifiOff, ServerCrash } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"

interface ErrorCardProps {
  /** The user-friendly error message */
  message?: string
  /** Optional description with more detail */
  description?: string
  /** Show a retry button */
  onRetry?: () => void
  /** Variant changes the icon and styling */
  variant?: "error" | "network" | "server"
  /** Optional className for the card */
  className?: string
}

const ICONS = {
  error: AlertCircle,
  network: WifiOff,
  server: ServerCrash,
}

/**
 * Reusable error card — consistent error display across all pages.
 *
 * Shows a friendly message, appropriate icon, and optional retry button.
 * NEVER shows technical error details to the user.
 */
export function ErrorCard({
  message = "Something went wrong",
  description = "Please try again or contact support if the problem persists.",
  onRetry,
  variant = "error",
  className = "",
}: ErrorCardProps) {
  const Icon = ICONS[variant]

  return (
    <Card className={`border-destructive/30 bg-destructive/5 ${className}`}>
      <CardContent className="flex flex-col items-center justify-center py-10 text-center">
        <div className="rounded-full bg-destructive/10 p-3 mb-3">
          <Icon className="h-5 w-5 text-destructive" />
        </div>
        <h3 className="text-base font-semibold mb-1">{message}</h3>
        <p className="text-sm text-muted-foreground mb-4 max-w-md">
          {description}
        </p>
        {onRetry && (
          <Button variant="outline" size="sm" onClick={onRetry}>
            <RefreshCw className="h-4 w-4 mr-2" />
            Try Again
          </Button>
        )}
      </CardContent>
    </Card>
  )
}

export default ErrorCard
