const API_BASE_URL = import.meta.env.VITE_API_URL || ""

interface RequestOptions extends RequestInit {
  params?: Record<string, string | number | boolean | null | undefined>
}

export async function apiClient<T>(
  endpoint: string,
  options: RequestOptions = {}
): Promise<T> {
  const { params, ...fetchOptions } = options

  let url = `${API_BASE_URL}${endpoint}`
  if (params) {
    const searchParams = new URLSearchParams()
    for (const [key, value] of Object.entries(params)) {
      if (value !== null && value !== undefined && value !== "") {
        searchParams.set(key, String(value))
      }
    }
    const queryString = searchParams.toString()
    if (queryString) {
      url += `?${queryString}`
    }
  }

  const response = await fetch(url, {
    headers: {
      "Content-Type": "application/json",
      ...fetchOptions.headers,
    },
    ...fetchOptions,
  })

  if (!response.ok) {
    const error = await response.json().catch(() => ({
      error: "Request failed",
      status: response.status,
    }))
    throw new Error(error.error || `API error: ${response.status}`)
  }

  return response.json()
}
