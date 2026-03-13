import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react"

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface User {
  email: string
  name: string
  role: "admin" | "viewer"
}

interface AuthContextType {
  user: User | null
  token: string | null
  isAuthenticated: boolean
  isLoading: boolean
  login: (email: string, password: string) => Promise<void>
  logout: () => void
}

// ---------------------------------------------------------------------------
// Context
// ---------------------------------------------------------------------------

const AuthContext = createContext<AuthContextType | undefined>(undefined)

const API_BASE = import.meta.env.VITE_API_URL || ""
const TOKEN_KEY = "beacon_token"
const USER_KEY = "beacon_user"

// ---------------------------------------------------------------------------
// Provider
// ---------------------------------------------------------------------------

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [token, setToken] = useState<string | null>(null)
  const [isLoading, setIsLoading] = useState(true)

  // Persist token to sessionStorage
  const saveSession = useCallback((newToken: string, newUser: User) => {
    sessionStorage.setItem(TOKEN_KEY, newToken)
    sessionStorage.setItem(USER_KEY, JSON.stringify(newUser))
    setToken(newToken)
    setUser(newUser)
  }, [])

  const clearSession = useCallback(() => {
    sessionStorage.removeItem(TOKEN_KEY)
    sessionStorage.removeItem(USER_KEY)
    setToken(null)
    setUser(null)
  }, [])

  // Check for existing session on mount
  useEffect(() => {
    const checkSession = async () => {
      const storedToken = sessionStorage.getItem(TOKEN_KEY)
      if (!storedToken) {
        setIsLoading(false)
        return
      }

      try {
        const res = await fetch(`${API_BASE}/api/auth/me`, {
          headers: { Authorization: `Bearer ${storedToken}` },
        })

        if (res.ok) {
          const data = await res.json()
          setToken(storedToken)
          setUser(data.data.user)
        } else {
          // Token expired or invalid — clear it
          clearSession()
        }
      } catch {
        // Network error — clear stale token
        clearSession()
      } finally {
        setIsLoading(false)
      }
    }

    checkSession()
  }, [clearSession])

  // Login
  const login = useCallback(
    async (email: string, password: string) => {
      const res = await fetch(`${API_BASE}/api/auth/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password }),
      })

      if (!res.ok) {
        const errData = await res.json().catch(() => ({}))
        const message =
          errData?.detail?.error ||
          errData?.error ||
          "Invalid email or password."
        throw new Error(message)
      }

      const data = await res.json()
      saveSession(data.data.token, data.data.user)
    },
    [saveSession],
  )

  // Logout
  const logout = useCallback(() => {
    // Fire-and-forget server notification
    if (token) {
      fetch(`${API_BASE}/api/auth/logout`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
      }).catch(() => {})
    }
    clearSession()
  }, [token, clearSession])

  return (
    <AuthContext.Provider
      value={{
        user,
        token,
        isAuthenticated: !!user && !!token,
        isLoading,
        login,
        logout,
      }}
    >
      {children}
    </AuthContext.Provider>
  )
}

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

export function useAuth(): AuthContextType {
  const context = useContext(AuthContext)
  if (context === undefined) {
    throw new Error("useAuth must be used within an AuthProvider")
  }
  return context
}
