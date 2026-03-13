import { useState } from "react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import {
  useAlerts,
  useAlertStats,
  useGenerateDigest,
  useUpdateAlertStatus,
  useTriggerScrape,
} from "@/hooks/useRegulatory"
import { AlertTriangle, RefreshCw, FileText, CheckCircle, XCircle, Loader2 } from "lucide-react"

const STATUS_COLORS: Record<string, string> = {
  new: "bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200",
  reviewed: "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200",
  dismissed: "bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-400",
}

export default function Regulatory() {
  const [statusFilter, setStatusFilter] = useState<string | undefined>(undefined)
  const [selectedId, setSelectedId] = useState<number | null>(null)
  const [page, setPage] = useState(0)

  const { data: alertsRes, isLoading, error } = useAlerts(statusFilter, 20, page * 20)
  const { data: statsRes } = useAlertStats()
  const generateDigest = useGenerateDigest()
  const updateStatus = useUpdateAlertStatus()
  const triggerScrape = useTriggerScrape()

  const alerts = alertsRes?.data || []
  const stats = statsRes?.data
  const total = (alertsRes?.meta?.total as number) || 0

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Regulatory Tracker</h1>
          <p className="text-muted-foreground">BSEE Safety Alerts & Regulatory Changes</p>
        </div>
        <Button
          onClick={() => triggerScrape.mutate()}
          disabled={triggerScrape.isPending}
          variant="outline"
        >
          {triggerScrape.isPending ? (
            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
          ) : (
            <RefreshCw className="mr-2 h-4 w-4" />
          )}
          Check for Updates
        </Button>
      </div>

      {/* Stats Cards */}
      {stats && (
        <div className="grid grid-cols-4 gap-4">
          <Card className="cursor-pointer hover:border-primary" onClick={() => setStatusFilter(undefined)}>
            <CardContent className="pt-4">
              <div className="text-2xl font-bold">{stats.total}</div>
              <p className="text-xs text-muted-foreground">Total Alerts</p>
            </CardContent>
          </Card>
          <Card className="cursor-pointer hover:border-primary" onClick={() => setStatusFilter("new")}>
            <CardContent className="pt-4">
              <div className="text-2xl font-bold text-blue-600">{stats.new}</div>
              <p className="text-xs text-muted-foreground">New / Unreviewed</p>
            </CardContent>
          </Card>
          <Card className="cursor-pointer hover:border-primary" onClick={() => setStatusFilter("reviewed")}>
            <CardContent className="pt-4">
              <div className="text-2xl font-bold text-green-600">{stats.reviewed}</div>
              <p className="text-xs text-muted-foreground">Reviewed</p>
            </CardContent>
          </Card>
          <Card className="cursor-pointer hover:border-primary" onClick={() => setStatusFilter("dismissed")}>
            <CardContent className="pt-4">
              <div className="text-2xl font-bold text-gray-500">{stats.dismissed}</div>
              <p className="text-xs text-muted-foreground">Dismissed</p>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Alert List */}
      <div className="space-y-3">
        {isLoading && <p className="text-muted-foreground">Loading alerts...</p>}
        {error && <p className="text-destructive">Failed to load alerts: {(error as Error).message}</p>}
        {!isLoading && alerts.length === 0 && (
          <Card>
            <CardContent className="py-8 text-center text-muted-foreground">
              <AlertTriangle className="mx-auto h-8 w-8 mb-2" />
              <p>No alerts found. Click &quot;Check for Updates&quot; to scan for new BSEE Safety Alerts.</p>
            </CardContent>
          </Card>
        )}

        {alerts.map((alert) => (
          <Card
            key={alert.id}
            className={`cursor-pointer transition-colors hover:border-primary ${
              selectedId === alert.id ? "border-primary" : ""
            }`}
            onClick={() => setSelectedId(selectedId === alert.id ? null : alert.id)}
          >
            <CardHeader className="pb-2">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <CardTitle className="text-base">
                    Safety Alert {alert.alert_number}
                  </CardTitle>
                  <Badge className={STATUS_COLORS[alert.status] || ""} variant="secondary">
                    {alert.status}
                  </Badge>
                  {alert.has_digest && (
                    <Badge variant="outline" className="text-xs">
                      <FileText className="mr-1 h-3 w-3" /> Digest
                    </Badge>
                  )}
                </div>
                <span className="text-xs text-muted-foreground">
                  {alert.published_date || alert.created_at?.split("T")[0]}
                </span>
              </div>
              <p className="text-sm text-muted-foreground line-clamp-2">{alert.title}</p>
            </CardHeader>

            {selectedId === alert.id && (
              <CardContent className="space-y-4 border-t pt-4">
                {/* AI Summary */}
                {alert.ai_summary ? (
                  <div className="space-y-2">
                    <h4 className="font-semibold text-sm">AI Summary</h4>
                    <p className="text-sm">{alert.ai_summary}</p>
                    {alert.ai_impact && (
                      <>
                        <h4 className="font-semibold text-sm">Impact</h4>
                        <p className="text-sm">{alert.ai_impact}</p>
                      </>
                    )}
                    {alert.ai_action_items.length > 0 && (
                      <>
                        <h4 className="font-semibold text-sm">Action Items</h4>
                        <ul className="list-disc list-inside text-sm space-y-1">
                          {alert.ai_action_items.map((item, i) => (
                            <li key={i}>{item}</li>
                          ))}
                        </ul>
                      </>
                    )}
                  </div>
                ) : (
                  <Button
                    size="sm"
                    onClick={(e) => {
                      e.stopPropagation()
                      generateDigest.mutate(alert.id)
                    }}
                    disabled={generateDigest.isPending}
                  >
                    {generateDigest.isPending ? (
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    ) : (
                      <FileText className="mr-2 h-4 w-4" />
                    )}
                    Generate AI Digest
                  </Button>
                )}

                {/* Actions */}
                <div className="flex gap-2">
                  {alert.status !== "reviewed" && (
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={(e) => {
                        e.stopPropagation()
                        updateStatus.mutate({ alertId: alert.id, status: "reviewed" })
                      }}
                    >
                      <CheckCircle className="mr-1 h-4 w-4" /> Mark Reviewed
                    </Button>
                  )}
                  {alert.status !== "dismissed" && (
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={(e) => {
                        e.stopPropagation()
                        updateStatus.mutate({ alertId: alert.id, status: "dismissed" })
                      }}
                    >
                      <XCircle className="mr-1 h-4 w-4" /> Dismiss
                    </Button>
                  )}
                  {alert.source_url && (
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={(e) => {
                        e.stopPropagation()
                        window.open(alert.source_url, "_blank")
                      }}
                    >
                      View on BSEE
                    </Button>
                  )}
                </div>
              </CardContent>
            )}
          </Card>
        ))}
      </div>

      {/* Pagination */}
      {total > 20 && (
        <div className="flex justify-center gap-2">
          <Button
            variant="outline"
            size="sm"
            disabled={page === 0}
            onClick={() => setPage(page - 1)}
          >
            Previous
          </Button>
          <span className="text-sm text-muted-foreground self-center">
            Page {page + 1} of {Math.ceil(total / 20)}
          </span>
          <Button
            variant="outline"
            size="sm"
            disabled={(page + 1) * 20 >= total}
            onClick={() => setPage(page + 1)}
          >
            Next
          </Button>
        </div>
      )}
    </div>
  )
}
