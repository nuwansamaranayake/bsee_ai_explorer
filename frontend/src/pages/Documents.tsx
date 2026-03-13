import { useState } from "react"
import ReactMarkdown from "react-markdown"
import { Search, FileSearch, AlertCircle } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Card, CardContent } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import { Badge } from "@/components/ui/badge"
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group"
import { CitationCard } from "@/components/CitationCard"
import { useDocumentSearch, useDocumentStats } from "@/hooks/useDocuments"

const SUGGESTED_QUERIES = [
  "What caused the Deepwater Horizon explosion?",
  "BSEE recommendations for subsea BOP maintenance",
  "Gas release incidents involving production platforms",
  "Crane and lifting safety findings",
  "Well control incident investigation findings",
]

export default function Documents() {
  const [query, setQuery] = useState("")
  const [docType, setDocType] = useState<string | null>(null)

  const { data: statsData } = useDocumentStats()
  const {
    mutate: search,
    data: searchData,
    isPending,
    isError,
    error,
  } = useDocumentSearch()

  const stats = statsData?.data
  const result = searchData?.data

  const handleSearch = (q?: string) => {
    const searchQuery = q || query
    if (!searchQuery.trim()) return
    if (q) setQuery(q)
    search({ query: searchQuery, top_k: 5, doc_type: docType })
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter") handleSearch()
  }

  const hasSearched = !!result || isPending || isError

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold tracking-tight flex items-center gap-2">
          <FileSearch className="h-7 w-7" />
          Document Intelligence
        </h1>
        <p className="text-muted-foreground mt-1">
          Search and analyze BSEE Safety Alerts and Investigation Reports with AI.
        </p>
      </div>

      {/* Search bar */}
      <div className="flex gap-2">
        <Input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Search BSEE Safety Alerts and Investigation Reports..."
          className="flex-1"
          disabled={isPending}
        />
        <Button onClick={() => handleSearch()} disabled={isPending || !query.trim()}>
          <Search className="h-4 w-4 mr-2" />
          Search
        </Button>
      </div>

      {/* Filter + Stats row */}
      <div className="flex flex-wrap items-center justify-between gap-4">
        <ToggleGroup
          type="single"
          value={docType || "all"}
          onValueChange={(val) => setDocType(val === "all" ? null : val)}
        >
          <ToggleGroupItem value="all">All</ToggleGroupItem>
          <ToggleGroupItem value="safety_alert">Safety Alerts</ToggleGroupItem>
          <ToggleGroupItem value="investigation_report">Investigation Reports</ToggleGroupItem>
        </ToggleGroup>
        {stats && stats.total_chunks > 0 && (
          <p className="text-xs text-muted-foreground">
            Searching across {stats.total_documents} documents ({stats.total_chunks} indexed passages)
          </p>
        )}
      </div>

      {/* Empty corpus warning */}
      {stats && stats.total_chunks === 0 && (
        <Card>
          <CardContent className="p-6 text-center text-muted-foreground">
            <AlertCircle className="h-8 w-8 mx-auto mb-2" />
            <p className="font-medium">No documents indexed yet</p>
            <p className="text-sm mt-1">
              Run the ingestion pipeline to populate the document corpus.
            </p>
          </CardContent>
        </Card>
      )}

      {/* Empty state — suggested queries */}
      {!hasSearched && stats && stats.total_chunks > 0 && (
        <Card>
          <CardContent className="p-6 text-center space-y-4">
            <FileSearch className="h-10 w-10 mx-auto text-muted-foreground" />
            <div>
              <p className="font-medium">Try a search query</p>
              <p className="text-sm text-muted-foreground mt-1">
                Ask questions about BSEE safety findings, investigation outcomes, and regulatory recommendations.
              </p>
            </div>
            <div className="flex flex-wrap gap-2 justify-center">
              {SUGGESTED_QUERIES.map((q, i) => (
                <Badge
                  key={i}
                  variant="outline"
                  className="cursor-pointer hover:bg-muted transition-colors px-3 py-1.5"
                  onClick={() => handleSearch(q)}
                >
                  {q}
                </Badge>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Loading skeleton */}
      {isPending && (
        <Card>
          <CardContent className="p-6 space-y-3">
            <Skeleton className="h-4 w-3/4" />
            <Skeleton className="h-4 w-full" />
            <Skeleton className="h-4 w-5/6" />
            <Skeleton className="h-4 w-2/3" />
          </CardContent>
        </Card>
      )}

      {/* Error state */}
      {isError && (
        <Card>
          <CardContent className="p-6">
            <div className="flex items-center gap-2 text-destructive">
              <AlertCircle className="h-5 w-5 shrink-0" />
              <div>
                <p className="font-medium">Search failed</p>
                <p className="text-sm mt-1">
                  {error instanceof Error ? error.message : "An error occurred. Please try again."}
                </p>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* AI Answer */}
      {result && !isPending && (
        <Card>
          <CardContent className="p-6">
            <div className="prose prose-sm dark:prose-invert max-w-none">
              <ReactMarkdown>{result.answer}</ReactMarkdown>
            </div>
            <div className="flex items-center gap-4 pt-3 mt-3 border-t text-xs text-muted-foreground">
              <span>Query: &ldquo;{result.query}&rdquo;</span>
              <span>{result.citations.length} sources cited</span>
              <span>Generated: {new Date(result.generated_at).toLocaleString()}</span>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Citations */}
      {result && !isPending && result.citations.length > 0 && (
        <div className="space-y-3">
          <h2 className="text-lg font-semibold">Sources</h2>
          {result.citations.map((citation, i) => (
            <CitationCard
              key={i}
              title={citation.title}
              pageNumber={citation.page_number}
              relevanceScore={citation.relevance_score}
              excerpt={citation.excerpt}
              sourceFile={citation.source_file}
            />
          ))}
        </div>
      )}
    </div>
  )
}
