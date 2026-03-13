import { useState } from "react"
import ReactMarkdown from "react-markdown"
import { Sparkles, RefreshCw, Copy, Check, ChevronDown, ChevronRight, AlertCircle } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card"
import { useTrendAnalysis } from "@/hooks/useAnalyze"

interface AIBriefingPanelProps {
  operator: string | null
}

export function AIBriefingPanel({ operator }: AIBriefingPanelProps) {
  const [isExpanded, setIsExpanded] = useState(false)
  const [copied, setCopied] = useState(false)

  const {
    mutate: generateBriefing,
    data: briefingData,
    isPending,
    isError,
    error,
  } = useTrendAnalysis()

  const briefing = briefingData?.data

  const handleGenerate = () => {
    setIsExpanded(true)
    generateBriefing({
      operator: operator || undefined,
    })
  }

  const handleCopy = async () => {
    if (briefing?.briefing) {
      await navigator.clipboard.writeText(briefing.briefing)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    }
  }

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <button
              onClick={() => setIsExpanded(!isExpanded)}
              className="flex items-center gap-2 hover:text-foreground transition-colors"
            >
              {isExpanded ? (
                <ChevronDown className="h-4 w-4 text-muted-foreground" />
              ) : (
                <ChevronRight className="h-4 w-4 text-muted-foreground" />
              )}
              <Sparkles className="h-4 w-4 text-amber-500" />
              <CardTitle className="text-base">AI Safety Briefing</CardTitle>
            </button>
          </div>
          <div className="flex items-center gap-2">
            {briefing && (
              <Button
                variant="ghost"
                size="sm"
                onClick={handleCopy}
                className="h-8 gap-1.5"
              >
                {copied ? (
                  <>
                    <Check className="h-3.5 w-3.5" />
                    Copied
                  </>
                ) : (
                  <>
                    <Copy className="h-3.5 w-3.5" />
                    Copy
                  </>
                )}
              </Button>
            )}
            <Button
              size="sm"
              onClick={handleGenerate}
              disabled={isPending}
              className="h-8 gap-1.5"
            >
              {isPending ? (
                <>
                  <RefreshCw className="h-3.5 w-3.5 animate-spin" />
                  Analyzing...
                </>
              ) : briefing ? (
                <>
                  <RefreshCw className="h-3.5 w-3.5" />
                  Regenerate
                </>
              ) : (
                <>
                  <Sparkles className="h-3.5 w-3.5" />
                  Generate Briefing
                </>
              )}
            </Button>
          </div>
        </div>
        <CardDescription>
          {operator
            ? `AI-generated safety trend analysis for ${operator}`
            : "AI-generated safety trend analysis for all GoM operators"}
        </CardDescription>
      </CardHeader>

      {isExpanded && (
        <CardContent>
          {isPending && !briefing && (
            <div className="flex items-center justify-center gap-3 py-12 text-muted-foreground">
              <div className="relative">
                <Sparkles className="h-6 w-6 text-amber-500 animate-pulse" />
              </div>
              <span className="text-sm animate-pulse">Analyzing safety trends...</span>
            </div>
          )}

          {isError && (
            <div className="flex items-center gap-2 rounded-lg border border-destructive/50 bg-destructive/10 p-4 text-sm text-destructive">
              <AlertCircle className="h-4 w-4 shrink-0" />
              <div>
                <p className="font-medium">Failed to generate briefing</p>
                <p className="mt-1 text-xs opacity-80">
                  {error instanceof Error ? error.message : "The AI service may not be available. Check that ANTHROPIC_API_KEY is configured."}
                </p>
              </div>
            </div>
          )}

          {briefing && (
            <div className="space-y-3">
              <div className="prose prose-sm dark:prose-invert max-w-none">
                <ReactMarkdown>{briefing.briefing}</ReactMarkdown>
              </div>
              <div className="flex items-center gap-4 pt-2 border-t text-xs text-muted-foreground">
                <span>Operator: {briefing.operator}</span>
                <span>Period: {briefing.date_range}</span>
                <span>
                  Generated: {new Date(briefing.generated_at).toLocaleString()}
                </span>
              </div>
            </div>
          )}

          {!isPending && !isError && !briefing && (
            <div className="text-center py-8 text-muted-foreground text-sm">
              Click &quot;Generate Briefing&quot; to create an AI-powered safety trend analysis.
            </div>
          )}
        </CardContent>
      )}
    </Card>
  )
}
