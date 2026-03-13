import { Navigate } from "react-router-dom"
import { useAuth } from "@/contexts/AuthContext"
import { Loader2 } from "lucide-react"
import { Card, CardContent } from "@/components/ui/card"
import { ShieldAlert } from "lucide-react"

interface ProtectedRouteProps {
  children: React.ReactNode
  /** If set, only users with this role can access the route */
  requiredRole?: "admin" | "viewer"
}

/**
 * Route guard — redirects to /login if not authenticated.
 * Optionally restricts by role (shows access-denied message for wrong role).
 */
export function ProtectedRoute({ children, requiredRole }: ProtectedRouteProps) {
  const { isAuthenticated, isLoading, user } = useAuth()

  // Still checking session — show spinner
  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    )
  }

  // Not authenticated — redirect to login
  if (!isAuthenticated) {
    return <Navigate to="/login" replace />
  }

  // Role check — show access denied
  if (requiredRole === "admin" && user?.role !== "admin") {
    return (
      <div className="flex items-center justify-center min-h-[60vh] p-6">
        <Card className="max-w-md w-full">
          <CardContent className="flex flex-col items-center justify-center py-12 text-center">
            <div className="rounded-full bg-amber-100 dark:bg-amber-900/30 p-3 mb-4">
              <ShieldAlert className="h-6 w-6 text-amber-600 dark:text-amber-400" />
            </div>
            <h2 className="text-lg font-semibold mb-1">Access Restricted</h2>
            <p className="text-sm text-muted-foreground">
              This page is only available to administrators.
              Contact your system administrator for access.
            </p>
          </CardContent>
        </Card>
      </div>
    )
  }

  return <>{children}</>
}
