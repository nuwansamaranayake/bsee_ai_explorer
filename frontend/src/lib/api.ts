/**
 * Centralized API client with enterprise error handling.
 *
 * - Catches ALL network/HTTP errors and translates them to user-friendly messages
 * - Includes request timeouts (30s default, 120s for AI endpoints)
 * - Never exposes raw Error objects, status codes, or technical details to the UI
 * - All errors thrown are clean Error instances with user-facing messages
 * - Injects Authorization header from sessionStorage for authenticated requests
 * - Handles 401 responses by clearing session and redirecting to /login
 */

const API_BASE_URL = import.meta.env.VITE_API_URL || ""
const TOKEN_KEY = "beacon_token"
const USER_KEY = "beacon_user"

/** Default timeout for API requests (ms) */
const DEFAULT_TIMEOUT_MS = 30_000
/** Extended timeout for AI-powered endpoints (ms) */
const AI_TIMEOUT_MS = 120_000

/** Endpoints that need extended timeouts (AI analysis, report generation) */
const AI_ENDPOINT_PATTERNS = [
  "/api/analyze",
  "/api/chat",
  "/api/documents/search",
  "/api/reports/generate",
  "/api/regulatory/digest",
]

interface RequestOptions extends RequestInit {
  params?: Record<string, string | number | boolean | null | undefined>
  /** Override the default timeout (ms) */
  timeout?: number
}

/** Extract a user-friendly error message from a backend response */
function extractErrorMessage(data: unknown, status: number): string {
  if (data && typeof data === "object") {
    const obj = data as Record<string, unknown>

    // Our standard error envelope: { error: "message", status: 400 }
    if (typeof obj.error === "string") return obj.error

    // FastAPI detail field (sometimes nested)
    if (typeof obj.detail === "string") return obj.detail
    if (obj.detail && typeof obj.detail === "object") {
      const detail = obj.detail as Record<string, unknown>
      if (typeof detail.error === "string") return detail.error
      if (typeof detail.detail === "string") return detail.detail
    }
  }

  // Generic messages by status range
  if (status === 404) return "The requested data was not found."
  if (status === 422) return "Please check your input and try again."
  if (status === 429) return "Too many requests. Please wait a moment and try again."
  if (status >= 500) return "The server encountered an error. Please try again."
  if (status >= 400) return "The request could not be processed."

  return "An unexpected error occurred."
}

/**
 * Central API client. All API calls in the app go through this function.
 *
 * @throws {Error} with a user-friendly message (never raw technical details)
 */
export async function apiClient<T>(
  endpoint: string,
  options: RequestOptions = {},
): Promise<T> {
  const { params, timeout, ...fetchOptions } = options

  // Build URL with query params
  let url = `${API_BASE_URL}${endpoint}`
  if (params) {
    const searchParams = new URLSearchParams()
    for (const [key, value] of Object.entries(params)) {
      if (value !== null && value !== undefined && value !== "") {
        searchParams.set(key, String(value))
      }
    }
    const queryString = searchParams.toString()
    if (queryString) url += `?${queryString}`
  }

  // Determine timeout
  const isAIEndpoint = AI_ENDPOINT_PATTERNS.some((p) => endpoint.startsWith(p))
  const timeoutMs = timeout ?? (isAIEndpoint ? AI_TIMEOUT_MS : DEFAULT_TIMEOUT_MS)

  // Create AbortController for timeout
  const controller = new AbortController()
  const timeoutId = setTimeout(() => controller.abort(), timeoutMs)

  // Inject auth token from sessionStorage (if available)
  const token = sessionStorage.getItem(TOKEN_KEY)
  const authHeaders: Record<string, string> = token
    ? { Authorization: `Bearer ${token}` }
    : {}

  try {
    const response = await fetch(url, {
      headers: {
        "Content-Type": "application/json",
        ...authHeaders,
        ...fetchOptions.headers,
      },
      signal: controller.signal,
      ...fetchOptions,
    })

    clearTimeout(timeoutId)

    // 401 Unauthorized — session expired or invalid, redirect to login
    if (response.status === 401) {
      sessionStorage.removeItem(TOKEN_KEY)
      sessionStorage.removeItem(USER_KEY)
      // Only redirect if not already on the login page
      if (!window.location.pathname.startsWith("/login")) {
        window.location.href = "/login"
      }
      throw new Error("Session expired. Please sign in again.")
    }

    if (!response.ok) {
      // Try to parse error body
      let errorData: unknown = null
      try {
        errorData = await response.json()
      } catch {
        // Response wasn't JSON — that's fine
      }
      throw new Error(extractErrorMessage(errorData, response.status))
    }

    // Parse response
    const contentType = response.headers.get("content-type") || ""
    if (contentType.includes("application/json")) {
      return await response.json() as T
    }

    // Non-JSON response (shouldn't happen for our API, but handle gracefully)
    return (await response.text()) as unknown as T

  } catch (error) {
    clearTimeout(timeoutId)

    // Already a clean Error with user message (from our throw above)
    if (error instanceof Error) {
      // AbortError = timeout
      if (error.name === "AbortError") {
        throw new Error(
          isAIEndpoint
            ? "AI analysis is taking longer than expected. Please try again."
            : "Request timed out. Please try again.",
        )
      }

      // TypeError from fetch = network error (no connection, DNS failure, CORS)
      if (error instanceof TypeError && error.message.includes("fetch")) {
        throw new Error(
          "Unable to reach the server. Please check your connection.",
        )
      }

      // Re-throw our custom errors as-is
      throw error
    }

    // Unknown error type
    throw new Error("An unexpected error occurred. Please try again.")
  }
}
