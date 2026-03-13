import { useState } from "react"
import { FileText, ChevronDown, ChevronRight } from "lucide-react"
import { Card, CardContent } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"

interface CitationCardProps {
  title: string
  pageNumber: number
  relevanceScore: number
  excerpt: string
  sourceFile: string
}

function relevanceBadgeVariant(score: number): "default" | "secondary" | "destructive" {
  if (score >= 0.8) return "default"
  if (score >= 0.6) return "secondary"
  return "destructive"
}

export function CitationCard({
  title,
  pageNumber,
  relevanceScore,
  excerpt,
  sourceFile,
}: CitationCardProps) {
  const [expanded, setExpanded] = useState(false)
  const pct = Math.round(relevanceScore * 100)

  return (
    <Card
      className="cursor-pointer hover:bg-muted/50 transition-colors"
      onClick={() => setExpanded(!expanded)}
    >
      <CardContent className="p-4">
        <div className="flex items-start justify-between gap-3">
          <div className="flex items-start gap-3 min-w-0">
            <FileText className="h-5 w-5 mt-0.5 shrink-0 text-muted-foreground" />
            <div className="min-w-0">
              <p className="font-medium text-sm leading-tight truncate">{title}</p>
              <p className="text-xs text-muted-foreground mt-0.5">
                Page {pageNumber} &middot; {sourceFile}
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2 shrink-0">
            <Badge variant={relevanceBadgeVariant(relevanceScore)}>
              {pct}%
            </Badge>
            {expanded ? (
              <ChevronDown className="h-4 w-4 text-muted-foreground" />
            ) : (
              <ChevronRight className="h-4 w-4 text-muted-foreground" />
            )}
          </div>
        </div>

        {/* Preview — always show truncated */}
        <p className="text-xs text-muted-foreground mt-2 line-clamp-2">
          {excerpt}
        </p>

        {/* Expanded — full excerpt */}
        {expanded && (
          <div className="mt-3 pt-3 border-t">
            <p className="text-sm whitespace-pre-wrap">{excerpt}</p>
          </div>
        )}
      </CardContent>
    </Card>
  )
}
