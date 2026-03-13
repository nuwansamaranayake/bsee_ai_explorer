import { Component, type ReactNode } from "react"
import { AlertTriangle, RefreshCw } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"

interface ErrorBoundaryProps {
  children: ReactNode
  /** Optional custom fallback UI */
  fallback?: ReactNode
  /** Section name shown in the error message */
  section?: string
}

interface ErrorBoundaryState {
  hasError: boolean
  error: Error | null
}

/**
 * React Error Boundary — wraps sections to catch render crashes.
 *
 * Displays a clean error card with retry button instead of crashing
 * the entire app. Users NEVER see stack traces or technical errors.
 */
export class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  constructor(props: ErrorBoundaryProps) {
    super(props)
    this.state = { hasError: false, error: null }
  }

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { hasError: true, error }
  }

  componentDidCatch(error: Error, errorInfo: React.ErrorInfo): void {
    // Log to console for debugging only — users never see this
    console.error(
      `[ErrorBoundary${this.props.section ? `: ${this.props.section}` : ""}]`,
      error,
      errorInfo.componentStack,
    )
  }

  handleReset = (): void => {
    this.setState({ hasError: false, error: null })
  }

  render(): ReactNode {
    if (this.state.hasError) {
      if (this.props.fallback) {
        return this.props.fallback
      }

      return (
        <Card className="border-destructive/30 bg-destructive/5">
          <CardContent className="flex flex-col items-center justify-center py-12 text-center">
            <div className="rounded-full bg-destructive/10 p-3 mb-4">
              <AlertTriangle className="h-6 w-6 text-destructive" />
            </div>
            <h3 className="text-lg font-semibold mb-1">Something went wrong</h3>
            <p className="text-sm text-muted-foreground mb-4 max-w-md">
              {this.props.section
                ? `The ${this.props.section} section encountered an issue. Please try again.`
                : "An unexpected error occurred. Please try again."}
            </p>
            <Button
              variant="outline"
              size="sm"
              onClick={this.handleReset}
            >
              <RefreshCw className="h-4 w-4 mr-2" />
              Try Again
            </Button>
          </CardContent>
        </Card>
      )
    }

    return this.props.children
  }
}

export default ErrorBoundary
