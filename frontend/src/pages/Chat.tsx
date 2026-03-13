import { useState, useRef, useEffect, useCallback } from "react"
import ReactMarkdown from "react-markdown"
import { Send, Bot, User, ChevronDown, ChevronRight, RefreshCw, Database, Code } from "lucide-react"
import { Button } from "@/components/ui/button"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Skeleton } from "@/components/ui/skeleton"
import { sanitizeAIResponse } from "@/lib/sanitize"

const API_BASE = import.meta.env.VITE_API_URL || ""

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface ChatMessage {
  id: string
  role: "user" | "assistant"
  content: string
  sql?: string
  data?: Record<string, unknown>[]
  error?: boolean
  timestamp: Date
}

// ---------------------------------------------------------------------------
// Suggested questions
// ---------------------------------------------------------------------------

const SUGGESTED_QUESTIONS = [
  "What were the top 3 causes of gas releases in deepwater last year?",
  "Which operator had the most incidents in 2023?",
  "Compare Woodside's safety record to the GoM average",
  "Show me all fatal incidents in the last 5 years",
  "What's the trend in equipment failure incidents?",
]

// ---------------------------------------------------------------------------
// Chat message component
// ---------------------------------------------------------------------------

function AssistantMessage({ message }: { message: ChatMessage }) {
  const [showSql, setShowSql] = useState(false)
  const [showData, setShowData] = useState(false)

  return (
    <div className="flex gap-3 items-start">
      <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-muted">
        <Bot className="h-4 w-4" />
      </div>
      <div className="flex-1 space-y-2 max-w-[85%]">
        {/* SQL section (collapsed by default) */}
        {message.sql && (
          <button
            onClick={() => setShowSql(!showSql)}
            className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground transition-colors"
          >
            {showSql ? <ChevronDown className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />}
            <Code className="h-3 w-3" />
            Show SQL Query
          </button>
        )}
        {showSql && message.sql && (
          <pre className="bg-muted p-3 rounded-md text-xs overflow-x-auto font-mono">
            {message.sql}
          </pre>
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
// useChat hook — manages SSE connection, message state, streaming
// ---------------------------------------------------------------------------

function useChat() {
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [isLoading, setIsLoading] = useState(false)

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

    try {
      const response = await fetch(`${API_BASE}/api/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: text }),
      })

      if (!response.ok) {
        const errData = await response.json().catch(() => ({}))
        throw new Error(errData.detail?.detail || errData.detail || `HTTP ${response.status}`)
      }

      const reader = response.body?.getReader()
      if (!reader) throw new Error("No response body")

      const decoder = new TextDecoder()
      let buffer = ""
      let sql = ""
      let data: Record<string, unknown>[] = []
      let answer = ""

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

            if (event.type === "sql") {
              sql = event.content
            } else if (event.type === "data") {
              data = event.content
            } else if (event.type === "answer" || event.type === "chunk") {
              answer += event.content
              // Update the assistant message progressively
              setMessages((prev) =>
                prev.map((m) =>
                  m.id === assistantId
                    ? { ...m, content: answer, sql, data }
                    : m
                )
              )
            } else if (event.type === "error") {
              answer = event.content
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
      setMessages((prev) =>
        prev.map((m) =>
          m.id === assistantId
            ? { ...m, content: answer || "No response received.", sql, data }
            : m
        )
      )
    } catch (error) {
      const errMsg = error instanceof Error ? error.message : "Unknown error"
      setMessages((prev) =>
        prev.map((m) =>
          m.id === assistantId
            ? {
                ...m,
                content: `I encountered an error: ${errMsg}. Please try again.`,
                error: true,
              }
            : m
        )
      )
    } finally {
      setIsLoading(false)
    }
  }, [])

  return { messages, isLoading, sendMessage }
}

// ---------------------------------------------------------------------------
// Chat Page
// ---------------------------------------------------------------------------

export default function Chat() {
  const { messages, isLoading, sendMessage } = useChat()
  const [input, setInput] = useState("")
  const scrollRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLTextAreaElement>(null)

  // Auto-scroll to bottom on new messages
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight
    }
  }, [messages])

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
          Ask questions about Gulf of Mexico safety data using natural language.
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
                  I can query the BSEE database, analyze trends, and compare operators.
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

          {/* Loading indicator */}
          {isLoading && messages[messages.length - 1]?.content === "" && (
            <div className="flex gap-3 items-start">
              <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-muted">
                <Bot className="h-4 w-4 animate-pulse" />
              </div>
              <div className="space-y-2">
                <Skeleton className="h-4 w-48" />
                <Skeleton className="h-4 w-36" />
              </div>
            </div>
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
