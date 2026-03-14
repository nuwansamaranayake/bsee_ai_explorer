import { useState, useRef, useEffect, useCallback } from "react"
import ReactMarkdown from "react-markdown"
import { Send, Bot, User, ChevronDown, ChevronRight, RefreshCw, Database, Code, Zap, BarChart3, GitCompareArrows } from "lucide-react"
import { Button } from "@/components/ui/button"
import { ScrollArea } from "@/components/ui/scroll-area"
import { sanitizeAIResponse } from "@/lib/sanitize"

const API_BASE = import.meta.env.VITE_API_URL || ""

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type Complexity = "simple" | "analytical" | "comparative"

interface ChatMessage {
  id: string
  role: "user" | "assistant"
  content: string
  sql?: string[]          // May have multiple queries now
  data?: Record<string, unknown>[]
  complexity?: Complexity
  error?: boolean
  timestamp: Date
}

// ---------------------------------------------------------------------------
// Suggested questions — showcase the intelligence engine
// ---------------------------------------------------------------------------

const SUGGESTED_QUESTIONS = [
  "Which companies have shown consistent safety improvement over the last decade?",
  "Compare BP vs Shell vs Chevron safety records 2018-2024",
  "What are the emerging incident trends in deepwater operations?",
  "Which operators have the worst violation-to-incident ratio?",
  "Is the Gulf of Mexico getting safer? Show me the evidence.",
  "What are the most common root causes of fatalities?",
  "Rank the top 10 operators by safety performance",
  "Which platforms are the most dangerous in the GoM?",
]

// ---------------------------------------------------------------------------
// Complexity badge
// ---------------------------------------------------------------------------

const COMPLEXITY_CONFIG: Record<Complexity, { label: string; icon: typeof Zap; className: string }> = {
  simple: {
    label: "Quick Lookup",
    icon: Zap,
    className: "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-500/20",
  },
  analytical: {
    label: "Multi-Query Analysis",
    icon: BarChart3,
    className: "bg-blue-500/10 text-blue-600 dark:text-blue-400 border-blue-500/20",
  },
  comparative: {
    label: "Comparative Analysis",
    icon: GitCompareArrows,
    className: "bg-purple-500/10 text-purple-600 dark:text-purple-400 border-purple-500/20",
  },
}

function ComplexityBadge({ complexity }: { complexity: Complexity }) {
  const config = COMPLEXITY_CONFIG[complexity]
  const Icon = config.icon
  return (
    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium border ${config.className}`}>
      <Icon className="h-3 w-3" />
      {config.label}
    </span>
  )
}

// ---------------------------------------------------------------------------
// Chat message components
// ---------------------------------------------------------------------------

function AssistantMessage({ message }: { message: ChatMessage }) {
  const [showSql, setShowSql] = useState(false)
  const [showData, setShowData] = useState(false)

  const queries = message.sql ?? []
  const hasQueries = queries.length > 0

  return (
    <div className="flex gap-3 items-start">
      <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-muted">
        <Bot className="h-4 w-4" />
      </div>
      <div className="flex-1 space-y-2 max-w-[85%]">
        {/* Complexity badge */}
        {message.complexity && (
          <ComplexityBadge complexity={message.complexity} />
        )}

        {/* SQL section (collapsed by default) */}
        {hasQueries && (
          <button
            onClick={() => setShowSql(!showSql)}
            className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground transition-colors"
          >
            {showSql ? <ChevronDown className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />}
            <Code className="h-3 w-3" />
            Show SQL {queries.length > 1 ? `Queries (${queries.length})` : "Query"}
          </button>
        )}
        {showSql && hasQueries && (
          <div className="space-y-2">
            {queries.map((sql, i) => (
              <div key={i}>
                {queries.length > 1 && (
                  <p className="text-[10px] text-muted-foreground font-medium mb-1">
                    Query {i + 1} of {queries.length}
                  </p>
                )}
                <pre className="bg-muted p-3 rounded-md text-xs overflow-x-auto font-mono">
                  {sql}
                </pre>
              </div>
            ))}
          </div>
        )}

        {/* Data section (collapsed by default) */}
        {message.data && message.data.length > 0 && (
          <>
            <button
              onClick={() => setShowData(!showData)}
              className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground transition-colors"
            >
              {showData ? <ChevronDown className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />}
              <Database className="h-3 w-3" />
              Show Data ({message.data.length} rows)
            </button>
            {showData && (
              <div className="overflow-x-auto max-h-64">
                <table className="w-full text-xs border-collapse">
                  <thead>
                    <tr className="border-b bg-muted/50">
                      {Object.keys(message.data[0]).map((col) => (
                        <th key={col} className="px-2 py-1 text-left font-medium">{col}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {message.data.slice(0, 20).map((row, i) => (
                      <tr key={i} className="border-b">
                        {Object.values(row).map((val, j) => (
                          <td key={j} className="px-2 py-1">{String(val ?? '')}</td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
                {message.data.length > 20 && (
                  <p className="text-xs text-muted-foreground mt-1 px-2">
                    Showing 20 of {message.data.length} rows
                  </p>
                )}
              </div>
            )}
          </>
        )}

        {/* Answer (always visible) */}
        <div className={`rounded-lg px-4 py-3 ${message.error ? "bg-destructive/10 text-destructive" : "bg-muted"}`}>
          <div className="prose prose-sm dark:prose-invert max-w-none">
            <ReactMarkdown>{sanitizeAIResponse(message.content)}</ReactMarkdown>
          </div>
        </div>
      </div>
    </div>
  )
}

function UserMessage({ message }: { message: ChatMessage }) {
  return (
    <div className="flex gap-3 items-start justify-end">
      <div className="max-w-[85%]">
        <div className="rounded-lg px-4 py-3 bg-primary text-primary-foreground">
          {message.content}
        </div>
      </div>
      <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-primary/10">
        <User className="h-4 w-4" />
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Phase loading indicator
// ---------------------------------------------------------------------------

function PhaseIndicator({ phase }: { phase: string }) {
  const phaseMessages: Record<string, string> = {
    planning: "Planning analysis approach...",
    planned: "Analysis planned",
    executing: "Running queries...",
    analyzing: "Analyzing results...",
  }
  const message = phaseMessages[phase] || phase

  return (
    <div className="flex gap-3 items-start">
      <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-muted">
        <Bot className="h-4 w-4 animate-pulse" />
      </div>
      <div className="flex items-center gap-2 py-2">
        <RefreshCw className="h-3.5 w-3.5 animate-spin text-muted-foreground" />
        <span className="text-sm text-muted-foreground">{message}</span>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// useChat hook — manages SSE connection, message state, streaming
// ---------------------------------------------------------------------------

function useChat() {
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [currentPhase, setCurrentPhase] = useState<string | null>(null)

  const sendMessage = useCallback(async (text: string) => {
    const userMsg: ChatMessage = {
      id: crypto.randomUUID(),
      role: "user",
      content: text,
      timestamp: new Date(),
    }

    // Placeholder assistant message for streaming
    const assistantId = crypto.randomUUID()
    const assistantMsg: ChatMessage = {
      id: assistantId,
      role: "assistant",
      content: "",
      timestamp: new Date(),
    }

    setMessages((prev) => [...prev, userMsg, assistantMsg])
    setIsLoading(true)
    setCurrentPhase("planning")

    try {
      // Inject auth token from sessionStorage (mirrors apiClient behavior)
      const token = sessionStorage.getItem("beacon_token")
      const authHeaders: Record<string, string> = {
        "Content-Type": "application/json",
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      }

      const response = await fetch(`${API_BASE}/api/chat`, {
        method: "POST",
        headers: authHeaders,
        body: JSON.stringify({ message: text }),
      })

      if (!response.ok) {
        // Handle 401 — session expired, redirect to login
        if (response.status === 401) {
          sessionStorage.removeItem("beacon_token")
          sessionStorage.removeItem("beacon_user")
          if (!window.location.pathname.startsWith("/login")) {
            window.location.href = "/login"
          }
          throw new Error("SESSION_EXPIRED")
        }

        // Try to extract user-friendly error message from backend
        const errData = await response.json().catch(() => ({}))
        const detail = errData?.detail
        const friendlyMsg = typeof detail === "string" ? detail : null
        throw new Error(friendlyMsg || `STATUS_${response.status}`)
      }

      const reader = response.body?.getReader()
      if (!reader) throw new Error("No response body")

      const decoder = new TextDecoder()
      let buffer = ""
      const sqlQueries: string[] = []
      let data: Record<string, unknown>[] = []
      let answer = ""
      let complexity: Complexity | undefined

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split("\n")
        buffer = lines.pop() || ""

        for (const line of lines) {
          if (!line.startsWith("data: ")) continue
          const jsonStr = line.slice(6).trim()
          if (!jsonStr) continue

          try {
            const event = JSON.parse(jsonStr)

            if (event.type === "phase") {
              // Update loading phase indicator
              setCurrentPhase(event.phase)
            } else if (event.type === "complexity") {
              complexity = event.content as Complexity
            } else if (event.type === "sql") {
              sqlQueries.push(event.content)
            } else if (event.type === "data") {
              data = event.content
            } else if (event.type === "answer" || event.type === "chunk") {
              answer += event.content
              setCurrentPhase(null) // Clear phase once answer starts
              // Update the assistant message progressively
              setMessages((prev) =>
                prev.map((m) =>
                  m.id === assistantId
                    ? { ...m, content: answer, sql: sqlQueries, data, complexity }
                    : m
                )
              )
            } else if (event.type === "error") {
              answer = event.content
              setCurrentPhase(null)
              setMessages((prev) =>
                prev.map((m) =>
                  m.id === assistantId
                    ? { ...m, content: answer, error: true }
                    : m
                )
              )
            }
          } catch {
            // Skip malformed SSE events
          }
        }
      }

      // Final update with all data
      setCurrentPhase(null)
      setMessages((prev) =>
        prev.map((m) =>
          m.id === assistantId
            ? { ...m, content: answer || "No response received.", sql: sqlQueries, data, complexity }
            : m
        )
      )
    } catch (error) {
      const rawMsg = error instanceof Error ? error.message : ""

      // Map internal error codes to user-friendly messages
      let userMessage: string
      if (rawMsg === "SESSION_EXPIRED") {
        userMessage = "Your session has expired. Please sign in again."
      } else if (rawMsg.startsWith("STATUS_")) {
        const status = parseInt(rawMsg.replace("STATUS_", ""), 10)
        if (status === 403) {
          userMessage = "You don't have permission to use this feature."
        } else if (status === 429) {
          userMessage = "Too many requests — please wait a moment and try again."
        } else if (status >= 500) {
          userMessage = "The server encountered an issue. Please try again in a moment."
        } else {
          userMessage = "Something went wrong processing your question. Please try rephrasing."
        }
      } else if (rawMsg.includes("fetch") || rawMsg.includes("NetworkError")) {
        userMessage = "Unable to reach the server. Please check your connection and try again."
      } else if (rawMsg) {
        userMessage = rawMsg
      } else {
        userMessage = "Something went wrong. Please try again."
      }

      setCurrentPhase(null)
      setMessages((prev) =>
        prev.map((m) =>
          m.id === assistantId
            ? { ...m, content: userMessage, error: true }
            : m
        )
      )
    } finally {
      setIsLoading(false)
      setCurrentPhase(null)
    }
  }, [])

  return { messages, isLoading, currentPhase, sendMessage }
}

// ---------------------------------------------------------------------------
// Chat Page
// ---------------------------------------------------------------------------

export default function Chat() {
  const { messages, isLoading, currentPhase, sendMessage } = useChat()
  const [input, setInput] = useState("")
  const scrollRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLTextAreaElement>(null)

  // Auto-scroll to bottom on new messages
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight
    }
  }, [messages, currentPhase])

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!input.trim() || isLoading) return
    sendMessage(input.trim())
    setInput("")
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault()
      handleSubmit(e)
    }
  }

  const isEmpty = messages.length === 0

  return (
    <div className="flex flex-col h-[calc(100vh-3rem)]">
      {/* Header */}
      <div className="border-b px-6 py-4">
        <h1 className="text-2xl font-bold tracking-tight flex items-center gap-2">
          <Bot className="h-6 w-6" />
          AI Safety Assistant
        </h1>
        <p className="text-muted-foreground text-sm mt-1">
          Ask questions about Gulf of Mexico safety data — from simple lookups to multi-query analysis.
        </p>
      </div>

      {/* Messages area */}
      <ScrollArea className="flex-1 px-6" ref={scrollRef}>
        <div className="max-w-3xl mx-auto py-6 space-y-6">
          {isEmpty && (
            <div className="text-center py-12 space-y-6">
              <div className="mx-auto w-16 h-16 rounded-full bg-muted flex items-center justify-center">
                <Bot className="h-8 w-8 text-muted-foreground" />
              </div>
              <div>
                <h2 className="text-lg font-semibold">Ask me anything about GoM safety data</h2>
                <p className="text-muted-foreground text-sm mt-1">
                  I can run multi-query analysis, compare operators, identify trends, and surface insights.
                </p>
              </div>

              {/* Suggested questions */}
              <div className="flex flex-wrap gap-2 justify-center max-w-xl mx-auto">
                {SUGGESTED_QUESTIONS.map((q, i) => (
                  <button
                    key={i}
                    onClick={() => {
                      setInput(q)
                      inputRef.current?.focus()
                    }}
                    className="text-xs px-3 py-2 rounded-full border bg-background hover:bg-muted transition-colors text-left"
                  >
                    {q}
                  </button>
                ))}
              </div>
            </div>
          )}

          {messages.map((msg) =>
            msg.role === "user" ? (
              <UserMessage key={msg.id} message={msg} />
            ) : (
              <AssistantMessage key={msg.id} message={msg} />
            )
          )}

          {/* Rich loading indicator with current phase */}
          {isLoading && currentPhase && (
            <PhaseIndicator phase={currentPhase} />
          )}
        </div>
      </ScrollArea>

      {/* Input area */}
      <div className="border-t px-6 py-4">
        <form onSubmit={handleSubmit} className="max-w-3xl mx-auto flex gap-2">
          <div className="flex-1 relative">
            <textarea
              ref={inputRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Ask about Gulf of Mexico safety data..."
              className="w-full resize-none rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50 min-h-[40px] max-h-[120px]"
              rows={1}
              disabled={isLoading}
            />
          </div>
          <Button type="submit" size="icon" disabled={isLoading || !input.trim()}>
            {isLoading ? (
              <RefreshCw className="h-4 w-4 animate-spin" />
            ) : (
              <Send className="h-4 w-4" />
            )}
          </Button>
        </form>
      </div>
    </div>
  )
}
