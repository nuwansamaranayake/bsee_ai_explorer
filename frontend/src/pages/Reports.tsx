import { useState } from "react"
import { FileText, Download, ExternalLink, Loader2, AlertCircle } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import { Label } from "@/components/ui/label"
import { Switch } from "@/components/ui/switch"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { useOperator } from "@/contexts/OperatorContext"
import { useOperators } from "@/hooks/useOperators"

const API_BASE = import.meta.env.VITE_API_URL || ""

const YEARS = Array.from({ length: 11 }, (_, i) => 2014 + i) // 2014-2024

interface RecentReport {
  operator: string | null
  yearStart: string | null
  yearEnd: string | null
  includeAI: boolean
  generatedAt: Date
  blobUrl: string
  filename: string
}

export default function Reports() {
  const { selectedOperator } = useOperator()
  const { data: operatorsData } = useOperators()
  const operators = operatorsData?.data ?? []

  const [operator, setOperator] = useState<string | null>(selectedOperator)
  const [yearStart, setYearStart] = useState<string | null>(null)
  const [yearEnd, setYearEnd] = useState<string | null>(null)
  const [includeAI, setIncludeAI] = useState(true)
  const [generating, setGenerating] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [recentReports, setRecentReports] = useState<RecentReport[]>([])

  const handleGenerate = async () => {
    setGenerating(true)
    setError(null)

    try {
      const response = await fetch(`${API_BASE}/api/reports/generate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          operator: operator || null,
          year_start: yearStart ? parseInt(yearStart) : null,
          year_end: yearEnd ? parseInt(yearEnd) : null,
          include_ai: includeAI,
        }),
      })

      if (!response.ok) {
        const errData = await response.json().catch(() => ({
          error: "Report generation failed",
        }))
        throw new Error(errData.detail?.detail || errData.detail || errData.error)
      }

      const blob = await response.blob()
      const blobUrl = URL.createObjectURL(blob)
      const opLabel = (operator || "gom_wide").toLowerCase().replace(/\s+/g, "_")
      const dateStr = new Date().toISOString().slice(0, 10)
      const filename = `beacon_gom_report_${opLabel}_${dateStr}.pdf`

      // Trigger download
      const a = document.createElement("a")
      a.href = blobUrl
      a.download = filename
      a.click()

      // Add to recent reports
      setRecentReports((prev) => [
        {
          operator,
          yearStart,
          yearEnd,
          includeAI,
          generatedAt: new Date(),
          blobUrl,
          filename,
        },
        ...prev,
      ])
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to generate report")
    } finally {
      setGenerating(false)
    }
  }

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold tracking-tight flex items-center gap-2">
          <FileText className="h-7 w-7" />
          Safety Report Generator
        </h1>
        <p className="text-muted-foreground mt-1">
          Generate professional PDF safety briefings with charts, data tables, and AI-written analysis.
        </p>
      </div>

      {/* Configuration form */}
      <Card>
        <CardHeader>
          <CardTitle>Report Configuration</CardTitle>
          <CardDescription>
            Customize the report scope and options.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          {/* Operator */}
          <div className="space-y-2">
            <Label>Operator</Label>
            <Select
              value={operator || "__gom_wide__"}
              onValueChange={(val) => setOperator(val === "__gom_wide__" ? null : val)}
            >
              <SelectTrigger>
                <SelectValue placeholder="Select operator" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="__gom_wide__">GoM-Wide (All Operators)</SelectItem>
                {operators.map((op) => (
                  <SelectItem key={op.name} value={op.name}>
                    {op.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {/* Year range */}
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label>Start Year</Label>
              <Select
                value={yearStart || "__all__"}
                onValueChange={(val) => setYearStart(val === "__all__" ? null : val)}
              >
                <SelectTrigger>
                  <SelectValue placeholder="All" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="__all__">All Years</SelectItem>
                  {YEARS.map((y) => (
                    <SelectItem key={y} value={String(y)}>
                      {y}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label>End Year</Label>
              <Select
                value={yearEnd || "__all__"}
                onValueChange={(val) => setYearEnd(val === "__all__" ? null : val)}
              >
                <SelectTrigger>
                  <SelectValue placeholder="All" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="__all__">All Years</SelectItem>
                  {YEARS.map((y) => (
                    <SelectItem key={y} value={String(y)}>
                      {y}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>

          {/* AI toggle */}
          <div className="flex items-center justify-between">
            <div className="space-y-0.5">
              <Label>Include AI Analysis</Label>
              <p className="text-xs text-muted-foreground">
                AI generates executive summary and recommendations. Takes 15-30 seconds longer.
              </p>
            </div>
            <Switch checked={includeAI} onCheckedChange={setIncludeAI} />
          </div>

          {/* Generate button */}
          <Button
            onClick={handleGenerate}
            disabled={generating}
            size="lg"
            className="w-full"
          >
            {generating ? (
              <>
                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                Generating report... This may take 15-30 seconds
              </>
            ) : (
              <>
                <FileText className="h-4 w-4 mr-2" />
                Generate Report
              </>
            )}
          </Button>

          {/* Error */}
          {error && (
            <div className="flex items-center gap-2 rounded-lg border border-destructive/50 bg-destructive/10 p-3 text-sm text-destructive">
              <AlertCircle className="h-4 w-4 shrink-0" />
              {error}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Recent reports */}
      {recentReports.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Recent Reports</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {recentReports.map((report, i) => (
                <div key={i} className="flex items-center justify-between p-3 rounded-lg border">
                  <div>
                    <p className="font-medium text-sm">{report.filename}</p>
                    <p className="text-xs text-muted-foreground">
                      {report.operator || "GoM-Wide"} &middot;{" "}
                      {report.yearStart || "All"} – {report.yearEnd || "All"} &middot;{" "}
                      {report.includeAI ? "With AI" : "Data only"} &middot;{" "}
                      {report.generatedAt.toLocaleTimeString()}
                    </p>
                  </div>
                  <div className="flex gap-2">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => {
                        const a = document.createElement("a")
                        a.href = report.blobUrl
                        a.download = report.filename
                        a.click()
                      }}
                    >
                      <Download className="h-3.5 w-3.5 mr-1" />
                      Download
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => window.open(report.blobUrl, "_blank")}
                    >
                      <ExternalLink className="h-3.5 w-3.5 mr-1" />
                      Preview
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  )
}
