import { useDataFreshness, useSchedulerStatus } from "@/hooks/useMonitoring"
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover"
import { Badge } from "@/components/ui/badge"
import { Database } from "lucide-react"

const DOT_COLORS = {
  fresh: "bg-green-500",
  stale: "bg-yellow-500",
  old: "bg-red-500",
  unknown: "bg-gray-400",
}

export function DataFreshness() {
  const { data: freshness } = useDataFreshness()
  const { data: schedulerRes } = useSchedulerStatus()
  const jobs = schedulerRes?.data || []

  const status = freshness?.status || "unknown"
  const label = freshness?.label || "Checking..."

  return (
    <Popover>
      <PopoverTrigger asChild>
        <button className="flex items-center gap-2 px-3 py-1.5 w-full text-left text-sm hover:bg-accent rounded-md transition-colors">
          <span className={`h-2 w-2 rounded-full ${DOT_COLORS[status]}`} />
          <Database className="h-3.5 w-3.5 text-muted-foreground" />
          <span className="text-muted-foreground">Data: {label}</span>
        </button>
      </PopoverTrigger>
      <PopoverContent align="start" className="w-72">
        <div className="space-y-2">
          <h4 className="font-semibold text-sm">ETL Job Status</h4>
          {jobs.length === 0 && (
            <p className="text-xs text-muted-foreground">No scheduled jobs found</p>
          )}
          {jobs
            .filter((j) => j.job_id !== "health_heartbeat")
            .map((job) => (
              <div key={job.job_id} className="flex items-center justify-between text-xs">
                <span className="truncate">{job.name}</span>
                <div className="flex items-center gap-1.5">
                  {job.last_run ? (
                    <Badge
                      variant={job.last_run.status === "success" ? "default" : "destructive"}
                      className="text-[10px] px-1 py-0"
                    >
                      {job.last_run.status}
                    </Badge>
                  ) : (
                    <Badge variant="secondary" className="text-[10px] px-1 py-0">
                      pending
                    </Badge>
                  )}
                </div>
              </div>
            ))}
        </div>
      </PopoverContent>
    </Popover>
  )
}
