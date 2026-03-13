import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import {
  useSystemHealth,
  useTokenUsage,
  useEndpointStats,
  useSchedulerStatus,
  useTriggerJob,
} from "@/hooks/useMonitoring"
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from "recharts"
import { Activity, Database, Cpu, DollarSign, Play, Loader2 } from "lucide-react"

export default function Monitoring() {
  const { data: healthRes, isLoading: healthLoading } = useSystemHealth()
  const { data: tokensRes } = useTokenUsage()
  const { data: endpointsRes } = useEndpointStats()
  const { data: schedulerRes } = useSchedulerStatus()
  const triggerJob = useTriggerJob()

  const health = healthRes?.data
  const tokens = tokensRes?.data
  const endpoints = endpointsRes?.data || []
  const jobs = schedulerRes?.data || []

  return (
    <div className="p-6 space-y-6">
      <div>
        <h1 className="text-2xl font-bold">System Monitoring</h1>
        <p className="text-muted-foreground">Health, performance, and cost tracking</p>
      </div>

      {/* System Health Row */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <Card>
          <CardContent className="pt-4">
            <div className="flex items-center gap-2">
              <Activity className="h-4 w-4 text-green-500" />
              <span className="text-xs text-muted-foreground">Uptime</span>
            </div>
            <div className="text-xl font-bold mt-1">
              {healthLoading ? "..." : health?.uptime_human || "N/A"}
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-4">
            <div className="flex items-center gap-2">
              <Database className="h-4 w-4 text-blue-500" />
              <span className="text-xs text-muted-foreground">DB Size</span>
            </div>
            <div className="text-xl font-bold mt-1">
              {health ? `${health.db_size_mb} MB` : "..."}
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-4">
            <div className="flex items-center gap-2">
              <Database className="h-4 w-4 text-purple-500" />
              <span className="text-xs text-muted-foreground">ChromaDB</span>
            </div>
            <div className="text-xl font-bold mt-1">
              {health ? `${health.chroma_chunks} chunks` : "..."}
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-4">
            <div className="flex items-center gap-2">
              <Cpu className="h-4 w-4 text-orange-500" />
              <span className="text-xs text-muted-foreground">Memory</span>
            </div>
            <div className="text-xl font-bold mt-1">
              {health ? `${health.memory_mb} MB` : "..."}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Token Usage + API Performance */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Token Usage */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <DollarSign className="h-4 w-4" />
              AI Token Usage (7-Day)
            </CardTitle>
          </CardHeader>
          <CardContent>
            {tokens?.today && (
              <div className="mb-4 grid grid-cols-3 gap-2 text-center">
                <div>
                  <div className="text-lg font-bold">{tokens.today.total_tokens.toLocaleString()}</div>
                  <div className="text-xs text-muted-foreground">Today&apos;s Tokens</div>
                </div>
                <div>
                  <div className="text-lg font-bold">${tokens.today.cost_usd.toFixed(4)}</div>
                  <div className="text-xs text-muted-foreground">Today&apos;s Cost</div>
                </div>
                <div>
                  <div className="text-lg font-bold">
                    {tokens.by_endpoint.length}
                  </div>
                  <div className="text-xs text-muted-foreground">Active Features</div>
                </div>
              </div>
            )}
            {tokens?.trend_7d && tokens.trend_7d.length > 0 ? (
              <ResponsiveContainer width="100%" height={200}>
                <BarChart data={tokens.trend_7d}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="date" tick={{ fontSize: 10 }} />
                  <YAxis tick={{ fontSize: 10 }} />
                  <Tooltip />
                  <Bar dataKey="total_tokens" fill="hsl(var(--primary))" name="Tokens" />
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <p className="text-sm text-muted-foreground text-center py-8">
                No token usage data yet
              </p>
            )}
          </CardContent>
        </Card>

        {/* API Performance */}
        <Card>
          <CardHeader>
            <CardTitle>API Performance</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="overflow-x-auto">
              <table className="w-full text-xs">
                <thead>
                  <tr className="border-b">
                    <th className="text-left py-1.5 pr-2">Endpoint</th>
                    <th className="text-right py-1.5 px-2">Reqs</th>
                    <th className="text-right py-1.5 px-2">P50</th>
                    <th className="text-right py-1.5 px-2">P95</th>
                    <th className="text-right py-1.5 px-2">Err%</th>
                  </tr>
                </thead>
                <tbody>
                  {endpoints.length === 0 && (
                    <tr>
                      <td colSpan={5} className="py-4 text-center text-muted-foreground">
                        No request data yet
                      </td>
                    </tr>
                  )}
                  {endpoints.slice(0, 15).map((ep) => (
                    <tr
                      key={ep.path}
                      className={`border-b ${ep.error_rate > 0.05 || ep.p95_ms > 2000 ? "bg-red-50 dark:bg-red-950" : ""}`}
                    >
                      <td className="py-1.5 pr-2 truncate max-w-[200px]">{ep.path}</td>
                      <td className="text-right py-1.5 px-2">{ep.request_count}</td>
                      <td className="text-right py-1.5 px-2">{ep.p50_ms}ms</td>
                      <td className="text-right py-1.5 px-2">{ep.p95_ms}ms</td>
                      <td className="text-right py-1.5 px-2">
                        {(ep.error_rate * 100).toFixed(1)}%
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* ETL Job Status */}
      <Card>
        <CardHeader>
          <CardTitle>Scheduled ETL Jobs</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b">
                  <th className="text-left py-2 pr-4">Job</th>
                  <th className="text-left py-2 px-4">Last Run</th>
                  <th className="text-left py-2 px-4">Status</th>
                  <th className="text-left py-2 px-4">Records</th>
                  <th className="text-left py-2 px-4">Next Run</th>
                  <th className="text-right py-2">Action</th>
                </tr>
              </thead>
              <tbody>
                {jobs.map((job) => (
                  <tr key={job.job_id} className="border-b">
                    <td className="py-2 pr-4 font-medium">{job.name}</td>
                    <td className="py-2 px-4 text-xs">
                      {job.last_run?.finished_at
                        ? new Date(job.last_run.finished_at).toLocaleString()
                        : "Never"}
                    </td>
                    <td className="py-2 px-4">
                      {job.last_run ? (
                        <Badge
                          variant={job.last_run.status === "success" ? "default" : "destructive"}
                        >
                          {job.last_run.status}
                        </Badge>
                      ) : (
                        <Badge variant="secondary">pending</Badge>
                      )}
                    </td>
                    <td className="py-2 px-4 text-xs">
                      {job.last_run?.records_processed ?? "-"}
                    </td>
                    <td className="py-2 px-4 text-xs">
                      {job.next_run ? new Date(job.next_run).toLocaleString() : "N/A"}
                    </td>
                    <td className="py-2 text-right">
                      <Button
                        size="sm"
                        variant="ghost"
                        onClick={() => triggerJob.mutate(job.job_id)}
                        disabled={triggerJob.isPending}
                      >
                        {triggerJob.isPending ? (
                          <Loader2 className="h-3 w-3 animate-spin" />
                        ) : (
                          <Play className="h-3 w-3" />
                        )}
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
