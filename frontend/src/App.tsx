import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { TooltipProvider } from "@/components/ui/tooltip"
import { SidebarProvider, SidebarInset, SidebarTrigger } from "@/components/ui/sidebar"
import { OperatorProvider } from "@/contexts/OperatorContext"
import { AppSidebar } from "@/components/AppSidebar"
import Dashboard from "@/pages/Dashboard"
import Compliance from "@/pages/Compliance"
import Chat from "@/pages/Chat"
import Documents from "@/pages/Documents"
import Reports from "@/pages/Reports"

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 5 * 60 * 1000,
      retry: 1,
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
            <Route path="/dashboard" element={<Dashboard />} />
            <Route path="/compliance" element={<Compliance />} />
            <Route path="/chat" element={<Chat />} />
            <Route path="/documents" element={<Documents />} />
            <Route path="/reports" element={<Reports />} />
          </Routes>
        </main>
      </SidebarInset>
    </SidebarProvider>
  )
}

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <TooltipProvider>
        <BrowserRouter>
          <OperatorProvider>
            <AppLayout />
          </OperatorProvider>
        </BrowserRouter>
      </TooltipProvider>
    </QueryClientProvider>
  )
}
