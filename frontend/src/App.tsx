import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { TooltipProvider } from "@/components/ui/tooltip"
import { SidebarProvider, SidebarInset, SidebarTrigger } from "@/components/ui/sidebar"
import { OperatorProvider } from "@/contexts/OperatorContext"
import { AppSidebar } from "@/components/AppSidebar"
import { ErrorBoundary } from "@/components/ErrorBoundary"
import Dashboard from "@/pages/Dashboard"
import Compliance from "@/pages/Compliance"
import Chat from "@/pages/Chat"
import Documents from "@/pages/Documents"
import Reports from "@/pages/Reports"
import Regulatory from "@/pages/Regulatory"
import Monitoring from "@/pages/Monitoring"

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 5 * 60 * 1000,    // 5 min before refetch
      gcTime: 30 * 60 * 1000,       // 30 min cache retention (survive API blips)
      retry: 2,                      // Retry failed queries twice
      retryDelay: (attempt: number) => Math.min(1000 * 2 ** attempt, 10000),
      refetchOnWindowFocus: false,   // Don't refetch on tab switch
    },
    mutations: {
      retry: 0,                      // Don't retry mutations
    },
  },
})

function AppLayout() {
  return (
    <SidebarProvider>
      <AppSidebar />
      <SidebarInset>
        <header className="flex h-12 items-center border-b px-4">
          <SidebarTrigger />
        </header>
        <main className="flex-1">
          <Routes>
            <Route path="/" element={<Navigate to="/dashboard" replace />} />
            <Route
              path="/dashboard"
              element={
                <ErrorBoundary section="Dashboard">
                  <Dashboard />
                </ErrorBoundary>
              }
            />
            <Route
              path="/compliance"
              element={
                <ErrorBoundary section="Compliance">
                  <Compliance />
                </ErrorBoundary>
              }
            />
            <Route
              path="/chat"
              element={
                <ErrorBoundary section="Chat">
                  <Chat />
                </ErrorBoundary>
              }
            />
            <Route
              path="/documents"
              element={
                <ErrorBoundary section="Documents">
                  <Documents />
                </ErrorBoundary>
              }
            />
            <Route
              path="/reports"
              element={
                <ErrorBoundary section="Reports">
                  <Reports />
                </ErrorBoundary>
              }
            />
            <Route
              path="/regulatory"
              element={
                <ErrorBoundary section="Regulatory">
                  <Regulatory />
                </ErrorBoundary>
              }
            />
            <Route
              path="/monitoring"
              element={
                <ErrorBoundary section="Monitoring">
                  <Monitoring />
                </ErrorBoundary>
              }
            />
          </Routes>
        </main>
      </SidebarInset>
    </SidebarProvider>
  )
}

export default function App() {
  return (
    <ErrorBoundary section="Application">
      <QueryClientProvider client={queryClient}>
        <TooltipProvider>
          <BrowserRouter>
            <OperatorProvider>
              <AppLayout />
            </OperatorProvider>
          </BrowserRouter>
        </TooltipProvider>
      </QueryClientProvider>
    </ErrorBoundary>
  )
}
