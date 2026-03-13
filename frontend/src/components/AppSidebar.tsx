import { useLocation, Link } from "react-router-dom"
import { useAuth } from "@/contexts/AuthContext"
import { UserMenu } from "@/components/UserMenu"
import {
  LayoutDashboard,
  ShieldCheck,
  MessageSquare,
  FileSearch,
  FileText,
  Sun,
  Moon,
  Monitor,
  AlertTriangle,
  Activity,
} from "lucide-react"
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarSeparator,
  useSidebar,
} from "@/components/ui/sidebar"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { Button } from "@/components/ui/button"
import { OperatorSelector } from "@/components/OperatorSelector"
import { DataFreshness } from "@/components/DataFreshness"
import { useEffect, useState } from "react"

// Brand assets — Vite resolves these to hashed URLs at build time
import logoDark from "@/assets/beacon_gom_logo_dark.png"
import iconSvg from "@/assets/beacon_gom_icon.svg"

const navItems = [
  { title: "Dashboard", path: "/dashboard", icon: LayoutDashboard },
  { title: "Compliance", path: "/compliance", icon: ShieldCheck },
  { title: "AI Chat", path: "/chat", icon: MessageSquare },
  { title: "Documents", path: "/documents", icon: FileSearch },
  { title: "Reports", path: "/reports", icon: FileText },
  { title: "Regulatory", path: "/regulatory", icon: AlertTriangle },
  { title: "Monitoring", path: "/monitoring", icon: Activity, adminOnly: true },
]

type Theme = "light" | "dark" | "system"

export function AppSidebar() {
  const location = useLocation()
  const { user } = useAuth()
  const { state } = useSidebar()
  const [theme, setTheme] = useState<Theme>("system")
  const isCollapsed = state === "collapsed"
  const isAdmin = user?.role === "admin"

  // Filter nav items — hide admin-only items for non-admin users
  const visibleNavItems = navItems.filter(
    (item) => !item.adminOnly || isAdmin,
  )

  useEffect(() => {
    const root = document.documentElement
    if (theme === "dark") {
      root.classList.add("dark")
    } else if (theme === "light") {
      root.classList.remove("dark")
    } else {
      const prefersDark = window.matchMedia("(prefers-color-scheme: dark)").matches
      root.classList.toggle("dark", prefersDark)
    }
  }, [theme])

  return (
    <Sidebar>
      <SidebarHeader>
        {/* Branded logo header */}
        <Link
          to="/dashboard"
          className="block focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring rounded-md"
        >
          {isCollapsed ? (
            /* Collapsed: show only the icon mark */
            <div className="flex items-center justify-center py-2">
              <img
                src={iconSvg}
                alt="Beacon GoM"
                className="h-8 w-8"
              />
            </div>
          ) : (
            /* Expanded: show full logo with navy background */
            <div className="rounded-lg overflow-hidden mx-1 my-1">
              <img
                src={logoDark}
                alt="Beacon GoM — AI Safety & Regulatory Intelligence"
                className="w-full h-auto"
                style={{ maxWidth: "180px" }}
              />
            </div>
          )}
        </Link>
        <SidebarSeparator />
        <OperatorSelector />
      </SidebarHeader>

      <SidebarContent>
        <SidebarGroup>
          <SidebarGroupLabel>Navigation</SidebarGroupLabel>
          <SidebarGroupContent>
            <SidebarMenu>
              {visibleNavItems.map((item) => (
                <SidebarMenuItem key={item.path}>
                  <SidebarMenuButton
                    asChild
                    isActive={location.pathname === item.path}
                  >
                    <Link to={item.path}>
                      <item.icon className="h-4 w-4" />
                      <span>{item.title}</span>
                    </Link>
                  </SidebarMenuButton>
                </SidebarMenuItem>
              ))}
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>
        <SidebarSeparator />
        <div className="px-2 py-1">
          <DataFreshness />
        </div>
      </SidebarContent>

      <SidebarFooter>
        <SidebarSeparator />
        <div className="px-2 py-1">
          <UserMenu />
        </div>
        <SidebarSeparator />
        <div className="px-2 py-2">
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="ghost" size="sm" className="w-full justify-start gap-2">
                {theme === "light" && <Sun className="h-4 w-4" />}
                {theme === "dark" && <Moon className="h-4 w-4" />}
                {theme === "system" && <Monitor className="h-4 w-4" />}
                <span className="capitalize">{theme} mode</span>
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="start">
              <DropdownMenuItem onClick={() => setTheme("light")}>
                <Sun className="mr-2 h-4 w-4" /> Light
              </DropdownMenuItem>
              <DropdownMenuItem onClick={() => setTheme("dark")}>
                <Moon className="mr-2 h-4 w-4" /> Dark
              </DropdownMenuItem>
              <DropdownMenuItem onClick={() => setTheme("system")}>
                <Monitor className="mr-2 h-4 w-4" /> System
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </SidebarFooter>
    </Sidebar>
  )
}
