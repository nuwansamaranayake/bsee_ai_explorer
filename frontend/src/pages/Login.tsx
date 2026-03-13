import { useState, type FormEvent } from "react"
import { useNavigate } from "react-router-dom"
import { useAuth } from "@/contexts/AuthContext"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Card, CardContent } from "@/components/ui/card"
import { Loader2, AlertCircle } from "lucide-react"

import iconSvg from "@/assets/beacon_gom_icon.svg"

export default function Login() {
  const { login } = useAuth()
  const navigate = useNavigate()

  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()
    setError(null)
    setLoading(true)

    try {
      await login(email, password)
      navigate("/dashboard", { replace: true })
    } catch (err) {
      setError(err instanceof Error ? err.message : "Invalid email or password.")
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex flex-col items-center justify-center px-4"
      style={{ background: "linear-gradient(180deg, #0A1628 0%, #0F2035 50%, #0A1628 100%)" }}
    >
      {/* Logo & Title */}
      <div className="mb-8 text-center">
        {/* Teal glow behind icon */}
        <div className="relative inline-block mb-4">
          <div
            className="absolute inset-0 blur-2xl opacity-30 rounded-full"
            style={{ background: "#0891B2" }}
          />
          <img
            src={iconSvg}
            alt="Beacon GoM"
            className="relative h-16 w-16 mx-auto"
          />
        </div>
        <h1 className="text-2xl font-bold text-white tracking-wide">
          BEACON GoM
        </h1>
        <p className="text-sm text-slate-400 mt-1">
          AI Safety & Regulatory Intelligence
        </p>
      </div>

      {/* Login Card */}
      <Card className="w-full max-w-sm border-slate-700/50 bg-slate-900/80 backdrop-blur-sm shadow-xl shadow-black/20">
        <CardContent className="pt-6 pb-6">
          <form onSubmit={handleSubmit} className="space-y-4">
            {/* Email */}
            <div className="space-y-2">
              <Label htmlFor="email" className="text-slate-300 text-sm">
                Email
              </Label>
              <Input
                id="email"
                type="email"
                placeholder="you@company.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                autoComplete="email"
                autoFocus
                className="bg-slate-800/50 border-slate-700 text-white placeholder:text-slate-500 focus-visible:ring-cyan-600"
              />
            </div>

            {/* Password */}
            <div className="space-y-2">
              <Label htmlFor="password" className="text-slate-300 text-sm">
                Password
              </Label>
              <Input
                id="password"
                type="password"
                placeholder="Enter your password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                autoComplete="current-password"
                className="bg-slate-800/50 border-slate-700 text-white placeholder:text-slate-500 focus-visible:ring-cyan-600"
              />
            </div>

            {/* Error */}
            {error && (
              <div className="flex items-center gap-2 rounded-lg border border-red-500/30 bg-red-500/10 p-3 text-sm text-red-400">
                <AlertCircle className="h-4 w-4 shrink-0" />
                {error}
              </div>
            )}

            {/* Submit */}
            <Button
              type="submit"
              disabled={loading}
              className="w-full font-medium text-white cursor-pointer"
              style={{ backgroundColor: "#0891B2" }}
            >
              {loading ? (
                <>
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                  Signing in...
                </>
              ) : (
                "Sign In"
              )}
            </Button>
          </form>
        </CardContent>
      </Card>

      {/* Footer */}
      <p className="mt-8 text-xs text-slate-500">
        &copy; 2026 AiGNITE Consulting | Houston, TX
      </p>
    </div>
  )
}
